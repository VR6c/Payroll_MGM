import hashlib
import logging
from django.conf import settings
from django.contrib.auth import logout
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('accounts')

class SecureSessionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            # Normalize IP address for local development
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
            if ip in ('127.0.0.1', '::1', 'localhost', '::ffff:127.0.0.1') or ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
                ip = '127.0.0.1'

            user_agent = request.META.get('HTTP_USER_AGENT', '')
            current_hash = hashlib.sha256(f"{ip}|{user_agent}".encode()).hexdigest()[:16]

            hashes = request.session.get('_security_hashes', [])
            if not hashes:
                stored_legacy = request.session.get('_security_hash')
                if stored_legacy:
                    hashes = [stored_legacy]
                else:
                    hashes = [current_hash]
                request.session['_security_hashes'] = hashes

            if current_hash not in hashes:
                if len(hashes) < 5:
                    hashes.append(current_hash)
                    request.session['_security_hashes'] = hashes
                else:
                    logger.warning(
                        f"Session security hash limit exceeded for user '{request.user.username}': "
                        f"current='{current_hash}' (IP={ip}, UA={user_agent})."
                    )
                    if not getattr(settings, 'DEBUG', True):
                        logout(request)
                        return

            request.session['_security_hash'] = current_hash


