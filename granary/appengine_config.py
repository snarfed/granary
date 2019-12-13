from oauth_dropins.appengine_config import *

# Suppress warnings. These are duplicated in oauth-dropins and bridgy; keep them
# in sync!
import warnings
warnings.filterwarnings('ignore', module='bs4',
                        message='No parser was explicitly specified')
warnings.filterwarnings('ignore',
                        message='URLFetch does not support granular timeout')
warnings.filterwarnings('ignore',
                        message='.*No parser was explicitly specified.*')
if DEBUG:
  warnings.filterwarnings('ignore', module='google.auth',
    message='Your application has authenticated using end user credentials')
