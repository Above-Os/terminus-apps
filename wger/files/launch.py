"""Olares launcher: stable signing keys and transactional first-install fixtures."""
import base64
import json
import os
from pathlib import Path
import sys

os.umask(0o077)
keys = Path('/home/wger/state/signing.private')
if not keys.exists():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    private = json.loads(RSAAlgorithm.to_jwk(rsa.generate_private_key(public_exponent=65537, key_size=2048)))
    private.update(alg='RS256', kid='wger')
    public = {k: private[k] for k in ('kty', 'n', 'e', 'alg', 'kid')}
    values = {name: base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
              for name, value in [('JWT_PRIVATE_KEY', private), ('JWT_PUBLIC_KEY', public)]}
    temporary = keys.with_suffix('.tmp')
    temporary.write_text(json.dumps(values))
    temporary.replace(keys)
os.environ.update(json.loads(keys.read_text()))
os.umask(0o022)

if sys.argv[1] == 'init':
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.db import transaction
    call_command('migrate', interactive=False)
    with transaction.atomic():
        if not get_user_model().objects.exists():
            fixtures = ['gym.json', 'languages.json', 'groups.json', 'users.json',
                        'licenses.json', 'setting_repetition_units.json', 'setting_weight_units.json',
                        'gym_config.json', 'equipment.json', 'muscles.json', 'categories.json',
                        'exercise-base-data.json', 'translations.json', 'gym-config.json', 'gym-adminconfig.json']
            for fixture in fixtures:
                call_command('loaddata', fixture, verbosity=0)
            user = get_user_model().objects.get(username='admin')
            user.set_password(os.environ['ADMIN_PASSWORD'])
            user.save(update_fields=['password'])
    # Fixtures bypass the profile-created signal; ensure its official category
    # through the upstream idempotent API without replacing user measurements.
    from wger.measurements.models import Category
    for user in get_user_model().objects.select_related('userprofile').all():
        Category.get_or_create_body_weight(user, unit=user.userprofile.weight_unit)
    call_command('set-site-url')
    call_command('collectstatic', interactive=False, verbosity=0)
    marker = Path('/home/wger/state/catalog-sync.complete')
    if not marker.exists():
        try:
            call_command('sync-exercises', dont_delete=True, verbosity=0)
            marker.touch()
        except Exception as error:
            print('Initial exercise catalog sync failed; retry at next startup:', type(error).__name__, flush=True)
    print('INITIALIZATION_COMPLETE', flush=True)
else:
    os.environ.pop('ADMIN_PASSWORD', None)
    os.execvp(sys.argv[1], sys.argv[1:])
