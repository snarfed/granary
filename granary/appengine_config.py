from oauth_dropins.appengine_config import *

# Suppress BeautifulSoup warning that we let it pick the XML parser instead of
# specifying one explicitly.
import warnings
warnings.filterwarnings('ignore', module='bs4', category=UserWarning)

# Additional ereporter exceptions to suppress.
ereporter_logging_handler.BLACKLIST += (
  'HTTPError: HTTP Error 401: Unauthorized',
  'HTTPError: HTTP Error 403: Forbidden',
)
