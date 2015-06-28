from oauth_dropins.appengine_config import *

# Suppress BeautifulSoup warning that we let it pick the XML parser instead of
# specifying one explicitly.
import warnings
warnings.filterwarnings('ignore', module='bs4', category=UserWarning)
