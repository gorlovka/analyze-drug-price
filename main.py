#!/usr/bin/env python
# encoding: utf8

import os
import os.path
import sys
import re
import json
from collections import namedtuple, OrderedDict, defaultdict

import requests

import pandas as pd


def bad_price_format(match):
    price = match.group(1)
    return ', "{}",'.format(price)


def remove_sep(match):
    cell = match.group(0)
    return cell.replace(',', '.')
    

# https://www.rosminzdrav.ru/opendata/7707778246-Gos%20reestr%20predel'nyh%20otpusknyh%20cen
def read_data(url="https://www.rosminzdrav.ru/opendata/7707778246-Gos%20reestr%20predel'nyh%20otpusknyh%20cen/data-20150610-structure-1.csv", path='data.csv'):
    response = requests.get(url)
    text = response.content
    text = text.decode('cp1251')
    data = []
    for line in text.split('\r\n'):
        if line:
            line = line.replace('\n', ' ')
            line = re.sub(r', ([\d ]+,\d+),', bad_price_format, line)
            line = line.replace('""', '')
            line = re.sub(r'"[^"]+"', remove_sep, line)
            row = [_.strip(' "') for _ in line.split(',')]
            name, title, dosage, producer, amount, price, _, id, date_code1, code2 = row
            if name in ('~', '-'):
                name = None
            if amount:
                amount = int(amount.replace(' ', ''))
            else:
                amount = None
            price = float(price.replace(' ', ''))
            if not id:
                id = None
            match = re.match('(\d\d.\d\d.\d\d\d\d)\s?\((.+)\)', date_code1)
            date, code1 = match.groups()
            date = pd.to_datetime(date)
            if not code2:
                code2 = None
            else:
                code2 = int(code2)
            data.append((name, title, dosage, amount, price, id, date, code1, code2))
    data = pd.DataFrame(
        data,
        columns=['name', 'title', 'dosage', 'amount',
                 'price', 'id', 'date', 'code1', 'code2']
    )
    return data


def get_max_prices(data):
    groups = defaultdict(lambda: defaultdict(list))
    for _, row in data.iterrows():
        groups[row.title][row.dosage, row.amount].append((row.date, row.price))
    prices = defaultdict(dict)
    for title, forms in groups.iteritems():
        for (form, amount), dates in forms.iteritems():
            _, price = max(dates)
            prices[title][form, amount] = price
    return prices


def list_serp_cache(cache):
    for filename in os.listdir(cache):
        yield filename.decode('utf8')


def get_serp(query, cache='serps', url=u'http://med.sputnik.ru/search?q={}'):
    serps = set(list_serp_cache(cache))
    path = os.path.join(cache, query)
    if query in serps:
        with open(path) as file:
            return file.read().decode('utf8')
    else:
        response = requests.get(url.format(query))
        print >>sys.stderr, 'Fetch', query
        with open(path, 'w') as file:
            file.write(response.content)
        return response.text


class Serp(OrderedDict):
    def _repr_pretty_(self, printer, _):
        for name, description in self.iteritems():
            printer.text(u'{}: {}\n'.format(name, description['title']))
            for id, form in description['forms'].iteritems():
                printer.text(u'  {}: {}\n'.format(id, form))


def parse_serp(content):
    serp = Serp()
    pattern = r'<a data-piwik="med.preparation" class="b-result-title__link" href="([^"]+)">([^<]+)</a>'
    for href, title in re.findall(pattern, content):
        name = re.match('/description/(\w+)\?', href).group(1)
        serp[name] = {
            'forms': OrderedDict(),
            'title': title
        }
    pattern = r'<a data-piwik="med.release_form" href="([^"]+)" class="[^"]+">(?:<img[^>]+>)?([^<]+)</a>'
    for href, form in re.findall(pattern, content):
        name, id = re.match('/description/(\w+)/(\d+)\?', href).groups()
        id = int(id)
        serp[name]['forms'][id] = form
    return serp


def search(query):
    return parse_serp(get_serp(query))


def load_serps(cache='serps'):
    return {_: search(_) for _ in list_serp_cache(cache)}


def get_prices(title, form=None, cache='prices', pattern='http://med.sputnik.ru/js_assortment?limit=950&extf_lat=55.75155956879236&extf_long=37.6186466217041&offset=0&radius=60000&q={}&form_id={}&orderby=distance_asc'):
    if form is None:
        name = title
        url = pattern.format(title, '')
    else:
        name = '{}_{}'.format(title, form)
        url = pattern.format(title, form)
    names = set(os.listdir(cache))
    path = os.path.join(cache, name)
    if name in names:
        with open(path) as file:
            return json.load(file)
    else:
        response = requests.get(url)
        print >>sys.stderr, 'Fetch', name
        with open(path, 'w') as file:
            file.write(response.content)
        return response.json()


class Price(namedtuple('Price', 'title, price, pharmacy')):
    def _repr_pretty_(self, printer, _):
        printer.text(u'{0.title}: {0.price}р ({0.pharmacy})'.format(self))


def parse_prices(data):
    for item in data['kmdata']['data']['response']['results']['items']:
        item = item['item']
        drug = item['drug']
        title = drug['name']
        price = float(drug['price'])
        pharmacy = item['pharmacy']['name']
        yield Price(title, price, pharmacy)


def unfold_pattern(pattern):
    mapping = {
        u'в/м': u'внутримышечного',
        u'д/в/м': u'для внутримышечного',
        u'д/в/в': u'для внутривенного',
        u'д/п/к': u'для подкожного',
        u'д/ингал.': u'для ингаляций',
        u'д/ингаляций': u'для ингаляций',
        u'д/инъекц.': u'для инъекций',
        u'д/инф': u'для инфузий',
        u'д/инф.': u'для инфузий',
        u'д/инфузий': u'для инфузий',
        u'д/наружн.': u'для наружного',
        u'д/местн.': u'для местного',
        u'д/пригот.': u'для приготовления',
        u'д/приема': u'для приема',
        u'капс.': u'капсулы',
        u'контролир.': u'контролируемым',
        u'конц.': u'концентрат',
        u'обол.': u'оболочкой',
        u'покр.': u'покрытые',
        u'прим.': u'применения',
        u'р-р': u'раствор',
        u'р-ра': u'раствора',
        u'сусп.': u'суспензия',
        u'таб.': u'таблетки',
    }
    words = pattern.split()
    words = [mapping.get(_, _) for _ in words]
    pattern = ' '.join(words)
    return pattern
    

def normalize_pattern(pattern):
    # Drug name goes first
    _, pattern = pattern.split(',', 1)
    pattern = pattern.translate({
        ord(','): None,
        ord('('): None,
        ord(')'): None
    })
    pattern = re.sub('\s\s+', ' ', pattern)
    pattern = pattern.strip()
    pattern = unfold_pattern(pattern)
    return pattern


def normalize_form(form):
    if '-' in form: 
        # Amount information goes after -
        form, _ = form.split('-', 1)
    form = form.translate({
        ord('['): None,
        ord(']'): None,
        ord('('): None,
        ord(')'): None,
        ord('|'): ord('/')
    })
    form = re.sub('\s\s+', ' ', form)
    form = form.strip()
    return form


def match_form(pattern, form):
    pattern = normalize_pattern(pattern)
    form = normalize_form(form)
    return form.startswith(pattern)


def match_forms(pattern, forms):
    match = {}
    for (form, amount), price in forms.iteritems():
        if match_form(pattern, form):
            match[form, amount] = price
    return match


def join_forms(serps, max_prices):
    not_found = set()
    no_forms = set()
    join = defaultdict(dict)
    for title, serp in serps.iteritems():
        if not serp:
            not_found.add(title)
        else:
            # Take into account only first result
            name, result = next(serp.iteritems())
            forms = result['forms']
            if not forms:
                no_forms.add(title)
            else:
                max = max_prices[title]
                for id, form in forms.iteritems():
                    match = match_forms(form, max)
                    join[name, title][id, form] = match
    return not_found, no_forms, join
        
