from oauth_dropins.appengine_config import *

# Add library modules directories to sys.path so they can be imported.
#
# I used to use symlinks and munge sys.modules, but both of those ended up in
# duplicate instances of modules, which caused problems. Background in
# https://github.com/snarfed/bridgy/issues/31
for path in (
  'beautifulsoup',
  'mf2py',
  ):
  path = os.path.join(os.path.dirname(__file__), path)
  if path not in sys.path:
    sys.path.append(path)


# Suppress BeautifulSoup warning that we let it pick the XML parser instead of
# specifying one explicitly.
import warnings
warnings.filterwarnings('ignore', module='bs4', category=UserWarning)
