#!/bin/bash
#
# Preprocesses docs and runs Sphinx (apidoc and build) to build the HTML docs.
#
# Requires:
#  brew install pandoc
#  pip install sphinx  (in virtualenv)
set -e

absfile=`readlink -f $0`
cd `dirname $absfile`

# generates the module index files:
#   docs/source/oauth_dropins.rst, oauth_dropins.webutil.rst
# only used to bootstrap. we've edited by hand since then so don't run any more
# or it will overwrite them.
# sphinx-apidoc -f -o source ../granary ../granary/tests

rm -f index.rst
cat > index.rst <<EOF
granary
=======

EOF

tail -n +19 ../README.md \
  | pandoc --from=markdown --to=rst \
  | sed -E 's/```/`/; s/`` </ </' \
  >> index.rst

source ../local/bin/activate

# Run sphinx in the virtualenv's python interpreter so it can import packages
# installed in the virtualenv.
python3 `which sphinx-build` -b html . _build/html
