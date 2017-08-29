#!/bin/bash
#
# Preprocesses docs and runs Sphinx (apidoc and build) to build the HTML docs.
set -e

absfile=`readlink -f $0`
cd `dirname $absfile`

# generates the module index files:
#   docs/source/oauth_dropins.rst, oauth_dropins.webutil.rst
# only used to bootstrap. we've edited by hand since ten so don't run any more
# or it will overwrite them.
# sphinx-apidoc -f -o source ../granary \
#   ../granary/{appengine_config.py,test}

rm -f index.rst
cat > index.rst <<EOF
granary documentation
=====================

EOF

tail -n +19 ../README.md \
  | pandoc --from=markdown --to=rst \
  | sed -E 's/```/`/; s/`` </ </' \
  >> index.rst

source ../local/bin/activate

# Run sphinx in the virtualenv's python interpreter so it can import packages
# installed in the virtualenv.
python `which sphinx-build` -b html . _build/html
