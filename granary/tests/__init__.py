import io, logging, os

from webutil.appengine_info import DEBUG

assert DEBUG
creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
assert not creds or creds.endswith('fake_user_account.json')

import sys
logging.basicConfig()
if '-v' in sys.argv:
    logging.getLogger().setLevel(logging.DEBUG)
else:
    handler = logging.getLogger().handlers[0]
    if hasattr(handler, 'setStream'):
        handler.setStream(io.StringIO())
