# gevent monkey patching
from gevent import monkey
monkey.patch_all()

#
import json
import falcon
import requests
import opengraph
import lxml
#import mf2py
from lxml.etree import tostring
from itertools import chain
from time import time
from bs4 import BeautifulSoup
from extruct.jsonld import JsonLdExtractor
from extruct.w3cmicrodata import MicrodataExtractor
from wsgiref import simple_server

#
try:
        from urlparse import urljoin  # Python2
except ImportError:
        from urllib.parse import urljoin  # Python3

###########################################
accepted_rel = ['icon', 'index', 'search', 'next', 'prev', 'canonical', 'license', 'pingback', 'author', 'publisher', 'shortlink', 'copyright']

def get_links(lxmldoc, url):
        result = dict()
        
        def parse(links):
                for link in links:
                        rel = link.get('rel').lower()
                        if rel in accepted_rel:
                                link_url = link.get('href')
                                if link.get('type') == 'application/opensearchdescription+xml' and rel=='search':
                                        rel = 'opensearch'
                                result[rel] = urljoin(url, link_url)
        
        parse(lxmldoc.xpath('.//link[@rel]'))
        parse(lxmldoc.xpath('.//a[@rel]'))

        return result


def fetch_metadata(url):
        before_request = time()
        response = requests.get(url, timeout=30)
        after_request = time()
        result = {'url': url, 'status': 'ok', 'size': len(response.text)}
        
        parser = lxml.html.HTMLParser(encoding=response.encoding)
        lxmldoc = lxml.html.fromstring(response.content, parser=parser)
        
        oge = opengraph.OpenGraph(lxml=lxmldoc)
        result['oge'] = oge
        
        mde = MicrodataExtractor(nested=True)
        data = mde.extract_items(lxmldoc, url)
        result['microdata'] = data
        
        jslde = JsonLdExtractor()
        data = jslde.extract_items(lxmldoc)
        result['json-ld'] = data
        
        result['links'] = get_links(lxmldoc, url)

        # mf = mf2py.parse(doc=response.text, html_parser='lxml')
        # result['microformat'] = mf
        
        after_parsing = time()
        
        result['time'] = {
                'get': after_request - before_request,
                'parsing': after_parsing - after_request,
                'total': after_parsing - before_request
        }
        return result


class MetadataParser(object):
        def on_get(self, req, resp):
                result = fetch_metadata(req.get_param('u', True))
                
                """Handles GET requests"""
                resp.status = falcon.HTTP_200  # This is the default status
                resp.body = json.dumps(result, sort_keys=True, indent=4, separators=(',', ': '))

app = falcon.API()
parser = MetadataParser()
app.add_route('/', parser)

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    httpd.serve_forever()

