#! python
"""
irbnet2csv

Merck, Spring 2018

TODO: Allow customized doc_types of interest
"""

from selenium import webdriver
import bs4
from dateutil import parser as dateparser
import unicodecsv as csv
from pprint import pprint
import time
import logging
import urlparse
import argparse
import yaml
import json
from datetime import datetime
import os

domain = "www.irbnet.org/release"
def url_for(path):
    return "https://{}/{}".format(domain, path)

def login(credentials):
    driver = webdriver.Chrome()

    url = url_for('j_security_check?j_username={}&j_password={}'.format(credentials['user'], credentials['password']))
    driver.get(url)
    return driver

def get_projects(driver):

    url = url_for('projects.do')
    driver.get(url)
    driver.execute_script("noOfRows='100'; displaySearchResults()")
    time.sleep(1)
    results = driver.find_element_by_id('searchResults')
    project_table = results.get_attribute('innerHTML')
    return project_table

def parse_project_table(project_table=None, fn=None):

    if not project_table and fn:
        with open(fn, "rU") as f:
            project_table = f.read()

    if not project_table:
        raise Exception("No project table")

    soup = bs4.BeautifulSoup(project_table, "lxml")
    data = []
    table_body = soup.find('tbody', attrs={'class':'yui-dt-data'})
    rows = table_body.find_all('tr')
    for row in rows:
        for anchor in row.findAll('a', href=True):

            url = urlparse.urlparse(anchor['href'])
            params = urlparse.parse_qs(url.query)
            if 'spk_id' in params:
                spk_id = params['spk_id'][0]

        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        cols = cols[1:-1]  # Get rid of flag and lock, but keep other empties
        cols = [spk_id] + cols
        data.append([ele for ele in cols])

    data_ = []
    for item in data:
        if len(item)<6:  # Some dead lines apparently w W+I projects
            logging.warn("Bad line: {}".format(item))
            continue
        item_ = {'spk_id': item[0],
                 'irbnet_id': item[1],
                 'short_title': item[2],
                 'pi': item[3],
                 'status': item[4],
                 'action': item[5],
                 'effective_date': item[6]}
        data_.append(item_)

    data = data_
    return data


def get_project_detail(driver, spk_id):

    url = url_for("study/overview.do?ctx_id=0&spk_id={}".format(spk_id))
    driver.get(url)
    time.sleep(1)

    undertitle = driver.find_element_by_id('toptitle')
    title = undertitle.get_attribute('title')

    element = driver.find_element_by_xpath("//*[@id='pagecenter']/table[2]")
    shared_with_table = element.get_attribute('innerHTML')

    detail = {'title': title}

    return detail, shared_with_table


def parse_shared_with_table(shared_with_table=None, fn=None):

    if not shared_with_table and fn:
        with open(fn, "rU") as f:
            shared_with_table = f.read()

    if not shared_with_table:
        raise Exception("No shared with table")

    soup = bs4.BeautifulSoup(shared_with_table, "lxml")
    data = []
    rows = soup.find_all('tr')
    for row in rows[1:]:
        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        data.append([ele for ele in cols if cols])

    data_ = []
    for item in data:
        data_.append(item[0])

    detail = {'shared_with': data_}
    return detail


def get_project_designer(driver, spk_id):

    url = url_for("study/designer.do?ctx_id=0&spk_id={}".format(spk_id))
    driver.get(url)
    time.sleep(1)

    # Find most recent protocol
    element = driver.find_element_by_xpath("//*[@id='pagecenter']")
    html = element.get_attribute('innerHTML')
    soup = bs4.BeautifulSoup(html, "lxml")
    data = []
    rows = soup.find_all('tr')
    for row in rows[1:]:
        doc_id = None

        for anchor in row.findAll('a', href=True):

            url = urlparse.urlparse(anchor['href'])
            params = urlparse.parse_qs(url.query)
            if 'doc_id' in params:
                doc_id = params['doc_id'][0]

        if not doc_id:
            continue

        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        if 'Protocol' in cols or 'Study Plan' in cols:
            data.append([doc_id]+[ele for ele in cols if cols][:-1])

    for item in data:
        date = dateparser.parse(item[-1])
        item.append(date)

    data.sort(key=lambda x: x[-1], reverse=True)

    item = data[0]

    if 'Protocol' in item:
        doc_name_index = item.index('Protocol') + 1
    else:
        doc_name_index = item.index('Study Plan') + 1

    protocol = {'doc_id': item[0],
                'date': item[-1],
                'doc_name': item[doc_name_index]}

    detail = {'protocol': protocol}
    return detail

def download_protocol(driver, doc_id):

    url = url_for("export/download.jsp?doc_id={}".format(doc_id))
    driver.get(url)

def write_yaml(projects, outfile):

    with open(outfile, "w") as f:
        yaml.safe_dump(projects, f)


def write_json(projects, outfile):

    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return json.JSONEncoder.default(self, obj)

    with open(outfile, "w") as f:
        json.dump(projects, f, indent=3, cls=DateTimeEncoder)


def write_csv(projects, outfile):

    for item in projects:
        if item.get('protocol'):
            item['protocol_doc'] = item['protocol']['doc_name']
            item['protocol_date'] = item['protocol']['date']

        if item.get('shared_with'):
            item['collaborators'] = ';'.join(item['shared_with'])

    fieldnames = [
        'title',
        'pi',
        'irbnet_id',
        'status',
        'effective_date',
        'collaborators',
        'protocol_doc',
        'protocol_date'
    ]

    with open(outfile, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(projects)

def parse_args():

    p = argparse.ArgumentParser(description='Scrape irbnet.org and format data into a standard format')
    p.add_argument("--user", "-u", required=True, help="irbnet.org credentials")
    p.add_argument("--password", "-p", required=True)
    p.add_argument("--outfile", "-o", help="extension must be 'csv', 'json', or 'yml'")
    p.add_argument("--download", "-d", action='store_true', help="download most recent protocol or study design document")

    opts = vars( p.parse_args() ) # Easier to treat as a dictionary

    return opts


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    opts = parse_args()

    # for testing:
    # with open('secrets.yml', 'r') as f:
    #     secrets = yaml.load(f)
    #     opts = secrets['opts']

    credentials = {"user": opts['user'],
                   "password": opts['password']}

    driver = login(credentials)

    project_table = get_projects(driver)
    projects = parse_project_table(project_table)

    # projects = parse_project_table(fn="samples/projects.html")
    for item in projects:
        detail, shared_with_table = get_project_detail(driver, item['spk_id'])
        item.update(detail)
        detail = parse_shared_with_table(shared_with_table)
        # detail = parse_shared_with_table(fn="samples/shared_with.html")
        item.update(detail)

        detail = get_project_designer(driver, item['spk_id'])
        item.update(detail)

        if opts['download']:
            download_protocol(driver, item['protocol']['doc_id'])

    driver.close()

    pprint(projects)

    if opts['outfile']:
        ext = os.path.splitext(opts['outfile'])[-1]

        logging.debug(ext)

        if ext == ".csv":
            write_csv(projects, opts['outfile'])
        elif ext == ".json":
            write_json(projects, opts['outfile'])
        elif ext == ".yml" or ext == ".yaml":
            write_yaml(projects, opts['outfile'])
        else:
            logging.warn("Unknown format {}".format(ext))

