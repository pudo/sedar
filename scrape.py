import os
import requests
import dataset
import urllib
from itertools import count
from urlparse import urljoin
from lxml import html
from datetime import datetime, timedelta
from slugify import slugify
from werkzeug.utils import secure_filename

INDUSTRIES = '046,047,005,006,058,025'
TO_DATE = datetime.utcnow()
FROM_DATE = TO_DATE - timedelta(days=10 * 365)
FROM_DATE = TO_DATE - timedelta(days=10)

SEARCH_PAGE = 'http://www.sedar.com/search/search_form_pc_en.htm'
RESULT_PAGE = 'http://www.sedar.com/FindCompanyDocuments.do'
PARAMS = {
    'lang': 'EN',
    'page_no': 2,
    'company_search': 'All (or type a name)',
    'document_selection': 0,
    'industry_group': INDUSTRIES,
    'FromDate': FROM_DATE.strftime('%d'),
    'FromMonth': FROM_DATE.strftime('%m'),
    'FromYear': FROM_DATE.strftime('%Y'),
    'ToDate': TO_DATE.strftime('%d'),
    'ToMonth': TO_DATE.strftime('%m'),
    'ToYear': TO_DATE.strftime('%Y'),
    'Variable': 'Issuer'
}

print PARAMS
engine = dataset.connect('postgresql://localhost/sedar')
filing = engine['filing']
company = engine['company']
sess = {}


def chomp_name(key):
    return slugify(key).replace('-', '_').strip('_')


def get_industries():
    res = requests.get(SEARCH_PAGE)
    doc = html.fromstring(res.content)
    for opt in doc.findall('.//select[@name="industry_group"]/option'):
        print opt.get('value'), ' -> ', opt.text_content().strip()


def get_company(url):
    if company.find_one(url=url):
        return
    res = requests.get(url)
    doc = html.fromstring(res.content)
    content = doc.find('.//div[@id="content"]')
    data = {'url': url, 'name': content.findtext('.//td/font/strong')}
    print 'Company', [data['name']]
    key = None
    for row in content.findall('.//td'):
        if row.get('class') == 'bt':
            key = chomp_name(row.text)
        elif row.get('class') == 'rt' and key is not None:
            data[key] = row.text
            key = None
        #print url, html.tostring(row)
    company.upsert(data, ['url'])


def download_document(form):
    file_name = form.split('/filings/', 1)[-1]
    filing_id, doc_id, rest = file_name.split('/', 2)
    rest = secure_filename(urllib.unquote(rest))
    file_name = os.path.join('filings', filing_id, doc_id, rest)
    if os.path.exists(file_name):
        return file_name

    from breaker import make_cracked_session
    print "Downloading", [form]
    if 'ca' not in sess or sess['ca'] is None:
        sess['ca'] = make_cracked_session()

    res = sess['ca'].get(form)
    if 'x-powered-by' in res.headers or \
            'Accept Terms of Use' in res.content:
        sess['ca'] = make_cracked_session()
        return download_document(form)

    try:
        os.makedirs(os.path.dirname(file_name))
    except:
        pass

    with open(file_name, 'wb') as fh:
        fh.write(res.content)

    return file_name


def load_filings():
    for i in count(1):
        page_hits = 0
        params = PARAMS.copy()
        params['page_no'] = i
        res = requests.get(RESULT_PAGE, params=params)
        doc = html.fromstring(res.content)

        for row in doc.findall('.//tr'):
            cells = row.findall('.//td')
            if len(cells) < 6:
                continue
            submit = cells[3].getchildren()[0].get('action')
            #print cells, html.tostring(row)
            if submit is None:
                continue
            page_hits += 1
            filing_id = submit.split('fileName=', 1)[-1]
            print 'Filing', [filing_id]
            form = urljoin(RESULT_PAGE, submit)
            file_name = download_document(form)
            data = {
                'filing': filing_id,
                'file_name': file_name,
                'company': cells[0].text_content().strip(),
                'company_url': urljoin(RESULT_PAGE, cells[0].find('./a').get('href')),
                'date': cells[1].text_content().strip(),
                'time': cells[2].text_content().strip(),
                'type': cells[3].text_content().strip(),
                'tos_form': form,
                'format': cells[4].text_content().strip(),
                'size': cells[5].text_content().strip()
            }
            filing.upsert(data, ['filing'])
            get_company(data['company_url'])

        if page_hits == 0:
            return


load_filings()
