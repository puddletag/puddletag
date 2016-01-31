TEMPLATE = """.. |source_link| replace:: puddletag-{version}.tar.gz
.. _source_link: https://github.com/keithgg/puddletag/releases/download/{version}/puddletag-{version}.tar.gz
.. |deb_link| replace:: puddletag_{version}-{deb_version}_all.deb
.. _deb_link: https://github.com/keithgg/puddletag/releases/download/{version}/puddletag_{version}-{deb_version}_all.deb
.. |deb_name| replace:: puddletag_{version}-{deb_version}_all.deb

.. |beta_source_link| replace:: puddletag-{version}.tar.gz
.. _beta_source_link: https://github.com/keithgg/puddletag/releases/download/{version}/puddletag_beta-{version}.tar.gz
.. |beta_deb_link| replace:: puddletag_{version}-{deb_version}_all.deb
.. _beta_deb_link: https://github.com/keithgg/puddletag/releases/download/{version}/dev/puddletag_beta_{version}-{deb_version}_all.deb

.. |source_sha| replace:: {source_sha}
.. |deb_sha| replace:: {deb_sha}
.. |beta_source_sha| replace:: {beta_source_sha}
.. |beta_deb_sha| replace:: {beta_deb_sha}

.. |version| replace:: {version}
.. |docs_html_link| replace:: HTML
.. _docs_html_link: https://github.com/keithgg/puddletag/releases/download/{version}/docs/puddletag-docs-html-{version}.tar.bz2
.. |docs_rst_link| replace:: ReStructuredText
.. _docs_rst_link: https://github.com/keithgg/puddletag/releases/download/{version}/docs/puddletag-docs-rst-{version}.tar.bz2


"""

import glob
import hashlib
import os
import sys

source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(source_dir, 'source'))

import puddlestuff

def get_sha1_sum(filename):
    with open(filename, 'rb') as fo:
        return hashlib.sha1(fo.read()).hexdigest()

def update_checksums(filename, build_dir):
    files = find_sources(build_dir)
    source_sha = get_sha1_sum(files['source'])
    deb_sha = get_sha1_sum(files['deb'])
    
    context = {
        'version': puddlestuff.version_string,
        'deb_version': "1",
        'source_sha': source_sha,
        'deb_sha': deb_sha,
        'beta_source_sha': source_sha,
        'beta_deb_sha': deb_sha
        
    }
    with open(filename, 'w') as fo:
        fo.write(TEMPLATE.format(**context))

def find_sources(build_dir):
    source_path = glob.glob(os.path.join(build_dir, '*.tar.gz'))[0]
    deb_path = glob.glob(os.path.join(build_dir, '*.deb'))[0]
    return {
        'source': source_path,
        'deb': deb_path
    }
    

if __name__ == '__main__':
    output = sys.argv[1]
    build_dir = sys.argv[2]
    update_checksums(output, build_dir)
    print "Checksums updated"
            
