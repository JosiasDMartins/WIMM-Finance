# finances/views/views_password_reset.py

import random
import string
from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from finances.models import PasswordResetCode

User = get_user_model()


def is_email_configured():
    """
    Check if email is properly configured.
    Returns True if EMAIL_HOST is set and not None.
    """
    return (
        hasattr(settings, 'EMAIL_HOST') and
        settings.EMAIL_HOST is not None and
        settings.EMAIL_HOST != ''
    )


def generate_reset_code(length=5):
    """Generate a random numeric code for password reset."""
    return ''.join(random.choices(string.digits, k=length))


def get_client_ip(request):
    """Get the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@csrf_protect
@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    """
    Step 1: User enters their username or email to request password reset.
    """
    # Block password reset in demo mode
    from django.conf import settings
    if getattr(settings, 'DEMO_MODE', False):
        messages.error(request, _('Password reset is disabled in demo mode.'))
        return redirect('login')

    # Check if email is configured
    if not is_email_configured():
        messages.error(request, _('Password reset is not available. Email system is not configured.'))
        return redirect('login')

    if request.method == 'POST':
        username_or_email = request.POST.get('username_or_email', '').strip()

        if not username_or_email:
            messages.error(request, _('Please enter your username or email.'))
            return render(request, 'finances/password_reset_request.html')

        # Try to find user by username or email
        user = None
        try:
            user = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                pass

        if not user:
            # Don't reveal if user exists or not (security)
            messages.info(request, _('If an account exists with that information, a verification code has been sent to the registered email address.'))
            return render(request, 'finances/password_reset_request.html')

        if not user.email:
            messages.error(request, _('This account does not have an email address registered. Please contact an administrator.'))
            return render(request, 'finances/password_reset_request.html')

        # Generate reset code
        code = generate_reset_code(getattr(settings, 'PASSWORD_RESET_CODE_LENGTH', 5))
        timeout = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600)  # Default 1 hour
        expires_at = timezone.now() + timedelta(seconds=timeout)

        # Invalidate any previous unused codes for this user
        PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)

        # Create new reset code
        reset_code = PasswordResetCode.objects.create(
            user=user,
            code=code,
            expires_at=expires_at,
            ip_address=get_client_ip(request)
        )

        # Send email
        try:
            subject = 'SweetMoney - Password Reset Verification Code'
            message = f'''Hello {user.username},

You have requested to reset your password for your SweetMoney account.

Your verification code is: {code}

This code will expire in {timeout // 60} minutes.

If you did not request this password reset, please ignore this email.

Best regards,
SweetMoney Team
'''
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sweetmoney.local')
            send_mail(
                subject,
                message,
                from_email,
                [user.email],
                fail_silently=False,
            )

            # Store user ID in session for next step
            request.session['password_reset_user_id'] = user.id
            request.session['password_reset_code_id'] = reset_code.id

            messages.success(request, _('A verification code has been sent to your email address.'))
            return redirect('password_reset_verify')

        except Exception as e:
            messages.error(request, _('Failed to send email. Please try again later or contact an administrator. Error: %(error)s') % {'error': str(e)})
            reset_code.delete()
            return render(request, 'finances/password_reset_request.html')

    return render(request, 'finances/password_reset_request.html')


@csrf_protect
@require_http_methods(["GET", "POST"])
def password_reset_verify(request):
    """
    Step 2: User enters the verification code sent to their email.
    """
    if not is_email_configured():
        messages.error(request, _('Password reset is not available.'))
        return redirect('login')

    # Check if user has a pending reset request
    user_id = request.session.get('password_reset_user_id')
    code_id = request.session.get('password_reset_code_id')

    if not user_id or not code_id:
        messages.error(request, _('No password reset request found. Please start the process again.'))
        return redirect('password_reset_request')

    try:
        user = User.objects.get(id=user_id)
        reset_code = PasswordResetCode.objects.get(id=code_id, user=user)
    except (User.DoesNotExist, PasswordResetCode.DoesNotExist):
        # Clear session
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_code_id', None)
        messages.error(request, _('Invalid reset request. Please start again.'))
        return redirect('password_reset_request')

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()

        if not entered_code:
            messages.error(request, _('Please enter the verification code.'))
            return render(request, 'finances/password_reset_verify.html')

        # Check if code is valid
        if not reset_code.is_valid():
            messages.error(request, _('This verification code has expired or been used. Please request a new one.'))
            # Clear session
            request.session.pop('password_reset_user_id', None)
            request.session.pop('password_reset_code_id', None)
            return redirect('password_reset_request')

        # Check if code matches
        if entered_code != reset_code.code:
            messages.error(request, _('Invalid verification code. Please try again.'))
            return render(request, 'finances/password_reset_verify.html')

        # Code is valid, proceed to password reset
        messages.success(request, _('Code verified! You can now set your new password.'))
        return redirect('password_reset_confirm')

    # Calculate remaining time
    remaining_seconds = max(0, int((reset_code.expires_at - timezone.now()).total_seconds()))
    remaining_minutes = remaining_seconds // 60

    context = {
        'remaining_minutes': remaining_minutes,
        'user_email': user.email[:3] + '***' + user.email[user.email.index('@'):] if '@' in user.email else '***'
    }

    return render(request, 'finances/password_reset_verify.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def password_reset_confirm(request):
    """
    Step 3: User sets their new password after verification.
    """
    if not is_email_configured():
        messages.error(request, _('Password reset is not available.'))
        return redirect('login')

    # Check if user has verified the code
    user_id = request.session.get('password_reset_user_id')
    code_id = request.session.get('password_reset_code_id')

    if not user_id or not code_id:
        messages.error(request, _('No verified reset request found. Please start the process again.'))
        return redirect('password_reset_request')

    try:
        user = User.objects.get(id=user_id)
        reset_code = PasswordResetCode.objects.get(id=code_id, user=user)
    except (User.DoesNotExist, PasswordResetCode.DoesNotExist):
        # Clear session
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_code_id', None)
        messages.error(request, _('Invalid reset request. Please start again.'))
        return redirect('password_reset_request')

    # Check if code is still valid
    if not reset_code.is_valid():
        messages.error(request, _('Your verification code has expired. Please request a new one.'))
        # Clear session
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_code_id', None)
        return redirect('password_reset_request')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # Validate passwords
        if not new_password or not confirm_password:
            messages.error(request, _('Please fill in both password fields.'))
            return render(request, 'finances/password_reset_confirm.html')

        if new_password != confirm_password:
            messages.error(request, _('Passwords do not match.'))
            return render(request, 'finances/password_reset_confirm.html')

        if len(new_password) < 8:
            messages.error(request, _('Password must be at least 8 characters long.'))
            return render(request, 'finances/password_reset_confirm.html')

        # Set new password
        user.set_password(new_password)
        user.save()

        # Mark code as used
        reset_code.mark_as_used(get_client_ip(request))

        # Clear session
        request.session.pop('password_reset_user_id', None)
        request.session.pop('password_reset_code_id', None)

        messages.success(request, _('Your password has been successfully reset! You can now log in with your new password.'))
        return redirect('login')

    return render(request, 'finances/password_reset_confirm.html', {'username': user.username})


@require_http_methods(["POST"])
def password_reset_resend_code(request):
    """
    Resend verification code to user's email.
    """
    if not is_email_configured():
        messages.error(request, _('Password reset is not available.'))
        return redirect('login')

    user_id = request.session.get('password_reset_user_id')

    if not user_id:
        messages.error(request, _('No password reset request found.'))
        return redirect('password_reset_request')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, _('User not found.'))
        return redirect('password_reset_request')

    # Generate new code
    code = generate_reset_code(getattr(settings, 'PASSWORD_RESET_CODE_LENGTH', 5))
    timeout = getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600)
    expires_at = timezone.now() + timedelta(seconds=timeout)

    # Invalidate previous codes
    PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)

    # Create new code
    reset_code = PasswordResetCode.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
        ip_address=get_client_ip(request)
    )

    # Send email
    try:
        subject = 'SweetMoney - Password Reset Verification Code (Resent)'
        message = f'''Hello {user.username},

Here is your new verification code for password reset:

{code}

This code will expire in {timeout // 60} minutes.

If you did not request this, please ignore this email.

Best regards,
SweetMoney Team
'''
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sweetmoney.local')
        send_mail(
            subject,
            message,
            from_email,
            [user.email],
            fail_silently=False,
        )

        # Update session with new code ID
        request.session['password_reset_code_id'] = reset_code.id

        messages.success(request, _('A new verification code has been sent to your email.'))
        return redirect('password_reset_verify')

    except Exception as e:
        messages.error(request, _('Failed to send email. Please try again later. Error: %(error)s') % {'error': str(e)})
        reset_code.delete()
        return redirect('password_reset_verify')
