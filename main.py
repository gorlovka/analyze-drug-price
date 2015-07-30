#!/usr/bin/env python
# encoding: utf8

import os
import os.path
import sys
import re
import json
from hashlib import md5
from collections import namedtuple, OrderedDict, defaultdict, Counter
from itertools import count

import requests
requests.packages.urllib3.disable_warnings()

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt


def bad_price_format(match):
    price = match.group(1)
    return ', "{}",'.format(price)


def remove_sep(match):
    cell = match.group(0)
    return cell.replace(',', '.')
    

# https://www.rosminzdrav.ru/opendata/7707778246-Gos%20reestr%20predel'nyh%20otpusknyh%20cen
# http://grls.rosminzdrav.ru/PriceLims.aspx?Torg=Палерол&Mnn=&Mnf=&Barcode=&Order=&All=0&PageSize=8&orderby=pklimprice&orderType=desc&pagenum=1
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


def read_xls_data(path='data.xls'):
    data = pd.read_excel('data.xls', header=2)
    data.columns = ['name', 'title', 'dosage', 'firm',
                    'amount', 'price', 'price2', 'id',
                    'date_code1', 'code2']
    data.name = [(None if _ in ('~', '-') else _) for _ in data.name]
    data.name = [(_.strip() if _ else None) for _ in data.name]
    data.title = [(_.strip() if _ else None) for _ in data.title]
    data.dosage = [(_.strip() if _ else None) for _ in data.dosage]
    dates = []
    codes = []
    for _ in data.date_code1:
        match = re.match('(\d\d.\d\d.\d\d\d\d)\s?\((.+)\)', _)
        date, code1 = match.groups()
        dates.append(date)
        codes.append(code1)
    data['date'] = pd.to_datetime(date)
    data['code1'] = codes
    del data['date_code1']
    return data


def get_max_prices(data):
    groups = defaultdict(lambda: defaultdict(list))
    for _, row in data.iterrows():
        groups[row.title][row.dosage, row.amount].append(row.price)
    prices = defaultdict(dict)
    for title, forms in groups.iteritems():
        for (form, amount), options in forms.iteritems():
            price = max(options)
            prices[title][form, amount] = price
    return prices


def get_title_hash(title):
    return md5(title.encode('utf8')).hexdigest()


def load_serp_cache(cache='serps', registry='registry.json'):
    with open(os.path.join(cache, registry)) as file:
        return json.load(file)


def dump_serp_cache(dump, cache='serps', registry='registry.json'):
    with open(os.path.join(cache, registry), 'w') as file:
        json.dump(dump, file)


def get_serp(query, cache='serps', pattern=u'http://med.sputnik.ru/search?q={}'):
    url = pattern.format(query)
    serps = load_serp_cache(cache)
    id = get_title_hash(query)
    path = os.path.join(cache, id)
    if id in serps:
        with open(path) as file:
            return file.read().decode('utf8')
    else:
        response = requests.get(url)
        print >>sys.stderr, 'Fetch', query
        with open(path, 'w') as file:
            file.write(response.content)
        serps[id] = query
        dump_serp_cache(serps)
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
    cache = load_serp_cache(cache)
    return {title: search(title) for id, title in cache.iteritems()}


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


def download_prices(join):
    prices = set()
    for (name, title), forms in join.iteritems():
        for (id, form), match in forms.iteritems():
            prices.add((name, id))
    for name, id in prices:
        get_prices(name, id)


class Price(namedtuple('Price', 'title, price, pharmacy')):
    def _repr_pretty_(self, printer, _):
        printer.text(u'{0.title}: {0.price}р ({0.pharmacy})'.format(self))


def get_price_amount(price):
    title = price.title
    match = re.search(r'n(\d+)x(\d+)', title)
    if match:
        amount1 = match.group(1)
        amount2 = match.group(2)
        try:
            return float(int(amount1) * int(amount2))
        except ValueError:
            return None
    matches = re.findall(ur'(?:х|№|/|n|\s)([\d\.]+)(?:,|\*|\(|\)|тб\.|таб|капс|шт|\s|$)', title)
    if matches:
        amount = matches[-1]
        try:
            return float(amount)
        except ValueError:
            return None
        


def parse_prices(data):
    if 'data' in data['kmdata']:
        response = data['kmdata']['data']['response']
        if 'results' in response:
            for item in response['results']['items']:
                item = item['item']
                drug = item['drug']
                title = drug['name']
                price = float(drug['price'])
                pharmacy = item['pharmacy']['name']
                yield Price(title, price, pharmacy)


def list_prices_cache(cache='prices'):
    for filename in os.listdir(cache):
        if '_' in filename:
            title, form = filename.rsplit('_', 1)
            form = int(form)
        else:
            title = filename
            form = None
        yield title, form


def load_prices(cache='prices'):
    return {(title, form): list(parse_prices(get_prices(title, form)))
            for title, form in list_prices_cache(cache)}


def deabbreviate_pattern(pattern):
    mapping = {
        u'в/м': u'внутримышечного',
        u'в/полостного': u'для полостного',
        u'в/сосудистого': u'внутрисосудистого',
        u'вагин.': u'вагинальные',
        u'введ.': u'введения',
        u'введен.': u'введения',
        u'высвоб.': u'высвобождением',
        u'высвобожден.': u'высвобождения',
        u'д/в': u'для внутрисосудистого',
        u'д/в/в': u'для внутривенного',
        u'д/в/м': u'для внутримышечного',
        u'д/вагинальн.': u'для вагинального',
        u'д/внутриглазного': u'для внутриглазного',
        u'д/внутрисосудистого': u'для внутрисосудистого',
        u'д/детей': u'для детей',
        u'д/и': u'для инъекций',
        u'д/инг.': u'для ингаляций',
        u'д/ингал.': u'для ингаляций',
        u'д/ингаляций': u'для ингаляций',
        u'д/интраназальн.': u'для интраназального',
        u'д/интраназального': u'для интраназального',
        u'д/инф': u'для инфузий',
        u'д/инф.': u'для инфузий',
        u'д/инфузий': u'для инфузий',
        u'д/инъекц.': u'для инъекций',
        u'д/инъекций': u'для инъекций',
        u'д/местн.': u'для местного',
        u'д/наружн.': u'для наружного',
        u'д/наружного': u'для наружного',
        u'д/п/к': u'для подкожного',
        u'д/парабульбарного': u'для парабульбарного',
        u'д/перитонеального': u'для перитонеального',
        u'д/пригот': u'для приготовления',
        u'д/пригот.': u'для приготовления',
        u'д/пригот.сусп.': u'для приготовления суспензии',
        u'д/приготов.': u'для приготовления',
        u'д/приема': u'для приема',
        u'д/рассасывания': u'для рассасывания',
        u'д/эндотрахеального': u'для эндотрахеального',
        u'действ.': u'действия',
        u'дозир.': u'дозированный',
        u'дозиров.': u'дозированный',
        u'замедл.': u'замедленным',
        u'ингал.': u'ингаляций',
        u'инъекц.': u'инъекций',
        u'инъекцион.': u'инъекционного',
        u'капс.': u'капсулы',
        u'кишечнораств.': u'кишечнорастворимой',
        u'компл.': u'комплекте',
        u'контролир.': u'контролируемым',
        u'конц.': u'концентрат',
        u'лек.': u'лекарственных',
        u'лиоф.': u'лиофилизат',
        u'местн.': u'местного',
        u'модиф.': u'модифицированным',
        u'модифиц.': u'модифицированным',
        u'модифицир.': u'модифицированным',
        u'наружн.': u'наружного',
        u'обол.': u'оболочкой',
        u'пленочн.': u'пленочной',
        u'подъязычн.': u'подъязычные',
        u'покр.': u'покрытые',
        u'пригот.': u'приготовления',
        u'прим.': u'применения',
        u'пролонг.': u'пролонгированного',
        u'пролонгир.': u'пролонгированного',
        u'р-р': u'раствор',
        u'р-ра': u'раствора',
        u'рект.': u'ректальные',
        u'ректальн.': u'ректального',
        u'супп.': u'суппозитории',
        u'сусп.': u'суспензия',
        u'таб.': u'таблетки',
    }
    words = pattern.split()
    words = [mapping.get(_, _) for _ in words]
    pattern = ' '.join(words)
    return pattern
    

def desynonymise_pattern(pattern):
    mapping = [
        (u'0.05%', u'0 05%'),
        (u'0.1%', u'0 1 %'),
        (u'0.1%', u'0.1 %'),
        (u'0.1%', u'0 1%'),
        (u'0.3%', u'0 3%'),
        (u'0.5%', u'0 5%'),
        (u'0.9%', u'0 9%'),
        (u'1.5%', u'1 5 %'),
        (u'10%', u'10 %'),
        (u'100мг/мл', u'100 мг/мл'),
        (u'5мг/мл', u'5 мг/мл'),
        (u'млн.КОЕ', u'млн КОЕ'),
        (u'млн.МЕ', u'млн МЕ'),
        (u'1 мл', u'мл'),
        (u'0 05%', u'0 05 %'),
        (u'0 05%', u'0.05%'),
        (u'0 1%', u'0 1 %'),
        (u'0 1%', u'0.1 %'),
        (u'0 1%', u'0.1%'),
        (u'0 3%', u'0.3%'),
        (u'0 5%', u'0 5 %'),
        (u'0 5%', u'0.5%'),
        (u'0 9%', u'0.9%'),
        (u'0.5 %', u'0 5%'),
        (u'0.5 г', u'0 5г'),
        (u'0.5 мг', u'0 5 мг'),
        (u'1 г', u'1 0 г'),
        (u'1 г', u'1000 мг'),
        (u'1 мг/мл', u'1 мг/1 мл'),
        (u'1.5 мг', u'1 5 мг'),
        (u'1.6 мг/мл', u'1 6 мг/мл'),
        (u'1.75 мг', u'1 75 мг'),
        (u'10 мг', u'10мг'),
        (u'10 тыс.КИЕ/мл', u'10 000 КИЕ/мл'),
        (u'100 МЕ/мл', u'100 ЕД/мл'),
        (u'100 мг', u'0 1г.'),
        (u'100 мг/мл', u'150 мг/1 5 мл'),
        (u'100 мкг', u'0.1 мг'),
        (u'100 мкг/мл', u'0.1 мг/мл'),
        (u'1000 МЕ', u'1 тыс.МЕ'),
        (u'12.5 мг', u'12 5 мг'),
        (u'125 мкг', u'0.125 мг'),
        (u'150 мкг', u'0.15 мг'),
        (u'16 мг', u'0.016 г'),
        (u'2.5 г', u'2 5 г'),
        (u'2.5 мг', u'2 5 мг'),
        (u'200 мг', u'200мг'),
        (u'200 мкг', u'0 2 мг'),
        (u'200 мкг/мл', u'0.2 мг/мл'),
        (u'250 мг', u'0 25 г'),
        (u'250 мг', u'250мг'),
        (u'250 мкг', u'0 25 мг'),
        (u'250 мкг/мл', u'0 25 мг/мл'),
        (u'3.5 мг', u'3 5 мг'),
        (u'300 мг', u'300мг'),
        (u'4 мг', u'4мг'),
        (u'40 мг/мл', u'80 мг/2 мл'),
        (u'400 мкг', u'0 4 мг'),
        (u'400 мкг', u'0 4 мг.'),
        (u'400 мкг', u'0 4мг'),
        (u'400 мкг', u'0.4 мг'),
        (u'50 мг/мл', u'50мг/мл'),
        (u'500 мг', u'0 5 г'),
        (u'500 мг', u'0 5 г.'),
        (u'500 мг', u'0 5г'),
        (u'500 мг', u'500мг'),
        (u'500 мг', u'500мг.'),
        (u'500 мкг', u'5 мг'),
        (u'500 мкг/мл', u'0.5 мг/мл'),
        (u'7.5 мг', u'7 5 мг'),
        (u'7.5 мг/мл', u'7 5 мг/мл'),
        (u'750 мкг', u'0.75 мг'),
        (u'8 мг', u'8мг'),
        (u'80 мг', u'80мг'),
        (u'800 мкг/мл', u'0.8 мг/мл'),
        (u'АЕ/1 доза', u'АЕ/доза'),
        (u'МЕ/0.5 мл', u'МЕ/0 5 мл'),
        (u'г/4 мл', u'г 4 мл'),
        (u'мг/ мл', u'мг/мл'),
        (u'мг/1 г', u'мг/г'),
        (u'мг/1 доза', u'мг/доза'),
        (u'мг/1.5 мл', u'мг 1.5 мл'),
        (u'мг/1.5 мл', u'мг/1 5 мл'),
        (u'мг/3 г', u'мг 3 г'),
        (u'мг/4 мл', u'мг 4 мл'),
        (u'мг/5 мл', u'мг 5 мл'),
        (u'мг/5 мл', u'мг/5мл'),
        (u'мкг/0.3 мл', u'мкг 0 3 мл'),
        (u'мкг/0.5 мл', u'мкг 0.5 мл'),
        (u'мкг/0.5 мл', u'мкг/0 5 мл'),
        (u'мкг/1 доза', u'мкг/доза'),
        (u'мл/1 доза', u'мл/доза'),
        (u'млн МЕ', u'млн. МЕ'),
        (u'млн МЕ', u'млн.МЕ'),
        (u'тыс.МЕ/1 г', u'тыс.МЕ/г'),
        (u'0.5 мг+0.25 мг/мл', u'0 25 мг/мл + 0 5 мг/мл'),
        (u'1 г+62.5 мг', u'1 000 мг+62.5 мг'),
        (u'1 г/10 мл', u'100 мг/мл'),
        (u'1 г/100 мл', u'10 мг/мл'),
        (u'1 г/20 мл', u'50 мг/мл'),
        (u'1 г/4 мл', u'250 мг/мл'),
        (u'1 г/5 мл', u'200 мг/мл'),
        (u'10 000 ЕД', u'10 тыс.ЕД'),
        (u'10 000 ЕД', u'10000 ЕД'),
        (u'10 г/200 мл', u'50 мг/мл'),
        (u'10 мг/10 мл', u'1 мг/мл'),
        (u'10 мг/2 мл', u'5 мг/мл'),
        (u'10 мг/50 мл', u'0.2 мг/мл'),
        (u'10 мкг/2 мл', u'5 мкг/мл'),
        (u'100 мг/10 мл', u'10 мг/мл'),
        (u'100 мг/100 мл', u'5 мг/5 мл'),
        (u'100 мг/16.7 мл', u'6 мг/мл'),
        (u'100 мг/2 мл', u'50 мг/мл'),
        (u'100 мг/5 мл', u'20 мг/мл'),
        (u'100 мг/50 мл', u'2 мг/мл'),
        (u'100 мкг/0.2 мл', u'0 1 мг/ 0 2 мл'),
        (u'100 мкг/0.2 мл', u'0.5 мг/мл 0.2 мл'),
        (u'100 мкг/1 доза', u'0.1 мг/доза'),
        (u'100 мкг/1 мл', u'0.1 мг/мл'),
        (u'150 000 МЕ', u'150 тыс.МЕ'),
        (u'150 мг+300 мг', u'300 мг+150 мг'),
        (u'150 мг/3 мл', u'50 мг/мл'),
        (u'160 мг/2 мл', u'80 мг/мл'),
        (u'2.5 мкг/1 доза', u'2 5 мкг/доза'),
        (u'2.8 мг/1 доза', u'2 8 мг/доза'),
        (u'20 мг/4 мл', u'5 мг/мл'),
        (u'200 мг/10 мл', u'20 мг/мл'),
        (u'200 мг/100 мл', u'2 мг/мл'),
        (u'200 мг/20 мл', u'10 мг/мл'),
        (u'200 мкг/1 доза', u'0 2 мг/доза'),
        (u'200 мкг/1 мл', u'0.2 мг/мл'),
        (u'25 мг/2 мл', u'12.5 мг/мл'),
        (u'25 мг/5 мл', u'5 мг/мл'),
        (u'250 мг/1 мл', u'250 мг 1 мл'),
        (u'250 мкг/0.5 мл', u'0 25 мг/0 5 мл'),
        (u'250 мкг/1 доза', u'0.1 мг/доза 200 доз'),
        (u'250 мкг/1 мл', u'0 25 мг/мл'),
        (u'300 мг/10 мл', u'30 мг/мл'),
        (u'300 мг/15 мл', u'300 мг 15 мл'),
        (u'300 мг/2 мл', u'150 мг/мл'),
        (u'300 мг/2 мл', u'150 мг/мл'),
        (u'300 мг/4 мл', u'75 мг/мл'),
        (u'300 мг/5 мл', u'60 мг/мл'),
        (u'300 мг/50 мл', u'6 мг/мл'),
        (u'300 мкг/0.6 мл', u'0.3 мг 0.6 мл'),
        (u'300 мкг/1 доза', u'0.3 мг/доза'),
        (u'4 г/10 мл', u'400 мг/мл'),
        (u'4 мг/2 мл', u'2 мг/мл'),
        (u'40 мг/2 мл', u'20 мг/мл'),
        (u'400 мг/10 мл', u'40 мг/мл'),
        (u'400 мг/250 мл', u'1.6 мг/мл'),
        (u'400 мг/4 мл', u'100 мг/мл'),
        (u'400 мкг/1 доза', u'0 4 мг/доза'),
        (u'45 мг/0.5 мл', u'45 мг/0 5 мл'),
        (u'450 мг/45 мл', u'10 мг/мл'),
        (u'5 г/100 мл', u'50 мг/мл'),
        (u'5 мг/100 мл', u'50 мкг/мл'),
        (u'5 мг/2 мл', u'2 5 мг/мл'),
        (u'5 мг/5 мл', u'1 мг/мл'),
        (u'5 мг/5 мл', u'5мг/5мл'),
        (u'5 млн.МЕ/1 мл', u'5 млн.МЕ 1 мл'),
        (u'5 тыс. МЕ', u'5000 МЕ'),
        (u'50 мг/0.5 мл', u'150 мг/1 5 мл'),
        (u'50 мг/10 мл', u'5 мг/мл'),
        (u'50 мг/2 мл', u'25 мг/мл'),
        (u'500 мг/100 мл', u'5 мг/мл'),
        (u'500 мг/2 мл', u'250 мг/мл'),
        (u'500 мг/3.3 мл', u'150 мг/мл'),
        (u'500 мг/5 мл', u'100 мг/мл'),
        (u'500 мкг/1 мл', u'0.5 мг/мл'),
        (u'500 мкг/2 мл', u'0.25 мг/мл'),
        (u'6 г/100 мл', u'60 мг/мл'),
        (u'600 мг/20 мл', u'30 мг/мл'),
        (u'600 мг/50 мл', u'12 мг/мл'),
        (u'66.7 г/100 мл', u'667 мг/мл'),
        (u'7.5 мг/1 мл', u'7 5 мг/мл'),
        (u'75 мг/0.75 мл', u'150 мг/1 5 мл'),
        (u'75 мг/3 мл', u'25 мг/мл'),
        (u'8 мг/4 мл', u'2 мг/мл'),
        (u'8 млн.МЕ/0.5 мл', u'8 млн. МЕ/0 5 мл'),
        (u'80 мг/2 мл', u'40 мг/мл'),
        (u'80 мг/4 мл', u'20 мг/мл'),
    ]
    for substring, replacement in mapping:
        if substring in pattern:
            yield pattern.replace(substring, replacement)
    yield pattern


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
    pattern = deabbreviate_pattern(pattern)
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
    return any(form.startswith(_)
               for _ in desynonymise_pattern(pattern))


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


def join_stats(serps, max_prices, not_found, no_forms, join):
    print 'Total:', len(serps)
    print 'Not found:', len(not_found)
    print 'No forms:', len(no_forms)
    print 'In join:', len(join)
    print

    total = 0
    matches = 0
    no_matches = {}
    coverage = 0
    for (name, title), forms in join.iteritems():
        for (id, form), match in forms.iteritems():
            total += 1
            if match:
                matches += 1
                coverage += len(match)
            else:
                no_matches[form] = max_prices[title]
    print 'Forms:', total
    print 'Matches:', matches
    print 'Data coverage:', coverage,
    return no_matches
    

def show_no_matches(no_matches):
    for pattern, forms in sorted(no_matches.iteritems()):
        print pattern
        for form, amount in sorted(forms)[:5]:
            print '  ', form, amount
        print


def show_join(join):
    for (name, title), forms in join.iteritems():
        print title
        for (id, pattern), match in forms.iteritems():
            if match:
                print '  ', pattern
                for (form, amount), price in match.iteritems():
                    print '    ', amount, price, form
        print


def show_small_diffs(no_matches, shift=4):
    synonyms = set()
    for pattern, forms in no_matches.iteritems():
        pattern = normalize_pattern(pattern)
        words = pattern.split()
        prefix = ' '.join(words[:-shift])
        rest = None
        for form, amount in forms:
            form = normalize_form(form)
            if form.startswith(prefix):
                rest = form[len(prefix):]
                break
        if rest:
            suffix = ' '.join(words[-shift:])
            synonyms.add((suffix, rest))

    for suffix, rest in sorted(synonyms):
        print suffix, ':', rest


def join_prices(join, prices):
    stats = defaultdict(dict)
    for (name, title), forms in join.iteritems():
        for (id, pattern), matches in forms.iteritems():
            max = defaultdict(dict)
            for (form, amount), price in matches.iteritems():
                max[amount][form] = price
            all = defaultdict(list)
            for option in prices[name, id]:
                amount = get_price_amount(option)
                if amount not in max:
                    amount = None
                if amount is None and 1.0 in max:
                    amount = 1.0
                all[amount].append(option)
            stats[name, title][id, pattern] = (max, all)
    return stats


def show_no_join(no_join):
    for form, (max, options) in no_join.iteritems():
        print form, '[' + ','.join(str(_) for _ in max.keys()) + ']'
        for option in options[:10]:
            print '  ', option.title
        print


def show_partial_join(partial_join):
    for form, (max, options) in partial_join.iteritems():
        print form, '[' + ','.join(str(_) for _ in max.keys()) + ']'
        for option in options[:10]:
            print '  ', option.title
        print


def stats_stats(stats):
    titles = 0
    total = 0
    have_max = 0
    joined = 0
    no_join = {}
    partial_join = {}
    for (name, title), forms in stats.iteritems():
        titles += 1
        for (id, form), (max, all) in forms.iteritems():
            total += 1
            if max:
                have_max += 1 
                if None not in all:
                    joined += 1
                else:
                    if len(all) == 1:
                        no_join[form] = (max, all[None])
                    else:
                        partial_join[form] = (max, all[None])
        
    print 'Titles:', titles
    print 'Forms:', total
    print 'Joined forms:', have_max
    print 'Clean join:', joined
    print 'No join', len(no_join)
    print 'Partial join', len(partial_join)
    return no_join, partial_join


def normalize_pharmacy(pharmacy):
    pharmacy = pharmacy.replace('&quot;', '"')
    pharmacy = pharmacy.replace(u'A5', u'А5')
    return pharmacy


def get_pharmacy_group(pharmacy):
    patterns = [
        u'А5',
        u'Аптечная сеть Оз',
        u'ГорФарма',
        u'Диасфарм',
        u'ЗАО Фирма Здоровье',
        u'Авиценна',
        u'МИЦАР',
        u'Маяк',
        u'Мебиус',
        u'ПРОГРЕСС-ФАРМА',
        u'С-ФАРМ',
        u'Фарматун',
        u'Феерия',
        u'Формула Здоровья',
        u'Сэсса Фарм',
        u'ИФК',
        u'Ригла',
        u'Фармакор',
        u'Фармастар',
        u'Формула Здоровья',
        u'НЕО-ФАРМ',
        u'Самсон-Фарма'
    ]
    pharmacy = normalize_pharmacy(pharmacy)
    for pattern in patterns:
        if pattern.lower() in pharmacy.lower():
            return pattern
    return pharmacy


def get_titles_popularity(stats, top=100):
    popular = Counter()
    for (name, title), forms in stats.iteritems():
        for (id, form), (max, all) in forms.iteritems():
            for amount in max:
                if amount in all:
                    popular[name, title, id, form, amount] = len(all[amount])
    filter = defaultdict(lambda: defaultdict(Counter))
    for (name, title, id, form, amount), popularity in popular.most_common(top):
        filter[name, title][id, form][amount] = popularity
    return filter
    

def plot_steps(smooth=False):
    fig, (ax1, ax2) = plt.subplots(1,2 )
    x = np.arange(0, 60, 0.01)
    y = [get_real_max_price(_, smooth=smooth) for _ in x]
    ax1.plot(x, y)
    x = np.arange(300, 600, 0.01)
    y = [get_real_max_price(_, smooth=smooth) for _ in x]
    ax2.plot(x, y)

    x = np.arange(0, 600, 0.01)
    for previous, current in zip(x, x[1:]):
        previous_real = get_real_max_price(previous, smooth=smooth)
        real = get_real_max_price(current, smooth=smooth)
        if real < previous_real:
            print '{}: {}, {}: {}'.format(previous, previous_real, current, real)


def dump_steps(path='viz/steps.json'):
    x = np.arange(0, 600, 1)
    steps = [
        {
            'x': _,
            'y': get_real_max_price(_, smooth=False)
        }
        for _ in x
    ]
    smooth = [
        {
            'x': _,
            'y': get_real_max_price(_, smooth=True)
        }
        for _ in x
    ]
    data = {
        'steps': steps,
        'smooth': smooth
    }
    with open(path, 'w') as dump:
        json.dump(data, dump)


def get_real_max_price(price, smooth=True, trace=False):
    nds = price * 1.10
    if nds <= 50.0:
        bulk = 0.2
        retail = 0.32
    elif nds <= 500.0:
        bulk = 0.15
        retail = 0.28
    else:
        bulk = 0.10
        retail = 0.15
    real = nds * (1 + bulk + retail)
    delta = 0
    if smooth:
        original = real
        if price > 45.45:
            real = max(real, 75.9924)
        if price > 454.54:
            real = max(real, 714.99142)
        delta = real - original
    if trace:
        return price, 0.10, bulk, retail, delta, real
    else:
        return real


def filter_stats(stats, filter):
    slice = defaultdict(dict)
    for (name, title), forms in stats.iteritems():
        if (name, title) in filter:
            for (id, form), (max, all) in forms.iteritems():
                if (id, form) in filter[name, title]:
                    amounts = filter[name, title][id, form]
                    max = {amount: forms for amount, forms
                           in max.iteritems() if amount in amounts}
                    all = {amount: prices for amount, prices
                           in all.iteritems() if amount in amounts}
                    slice[name, title][id, form] = (max, all)
    return slice


def shows_stats(stats):
    for (name, title), forms in stats.iteritems():
        print title
        for (id, form), (max, all) in forms.iteritems():
            print '  ', form
            for amount, forms in max.iteritems():
                for form, price in forms.iteritems():
                    print '    * ', amount, form, price, get_real_max_price(price)
                titles = Counter()
                options = Counter()
                for title, price, pharmacy in all[amount]:
                    titles[title] += 1
                    pharmacy = get_pharmacy_group(pharmacy)
                    options[pharmacy, price] += 1
                for title, count in titles.most_common(10):
                    print '    - ', count, '\t', title
                for (pharmacy, price), count in options.most_common(10):
                    print '    # ', count, '\t', pharmacy, price


def dump_stats(stats, path='viz/data.json'):
    pharmacies = defaultdict(count().next)
    dump = defaultdict(dict)
    for (name, title), forms in stats.iteritems():
        for (id, form), (max, all) in forms.iteritems():
            dump[name][id] = {
                'pattern': form,
                'title': title,
                'amounts': {}
            }
            for amount, limits in max.iteritems():
                limits = {form: get_real_max_price(price, smooth=True, trace=True)
                          for form, price in limits.iteritems()}
                prices = {}
                if amount in all:
                    for option in all[amount]:
                        pharmacy = normalize_pharmacy(option.pharmacy)
                        price = option.price
                        prices[pharmacies[pharmacy]] = price
                dump[name][id]['amounts'][amount] = {
                    'limits': limits,
                    'prices': prices
                }
    pharmacies = {id: pharmacy for pharmacy, id
                  in pharmacies.iteritems()}
    with open(path, 'w') as file:
        json.dump([pharmacies, dump], file)


def get_locations(cache='prices'):
    locations = {}
    coordinates = {}
    for title, form in list_prices_cache(cache):
        data = get_prices(title, form)
        if 'data' in data['kmdata']:
            response = data['kmdata']['data']['response']
            if 'results' in response:
                for item in response['results']['items']:
                    pharmacy = item['item']['pharmacy']
                    name = normalize_pharmacy(pharmacy['name'])
                    lat = pharmacy['latitude']
                    lon = pharmacy['longitude']
                    locations[name] = lat, lon
                    phone = pharmacy['phone']
                    address = pharmacy['address']
                    coordinates[name] = phone, address
    return locations, coordinates


def get_excesses(stats, locations):
    excesses = []
    for (name, title), forms in stats.iteritems():
        for (id, form), (maxes, all) in forms.iteritems():
            for amount, limits in maxes.iteritems():
                if amount in all:
                    limit = max(limits.values())
                    limit = get_real_max_price(limit)
                    for option in all[amount]:
                        price = option.price
                        pharmacy = normalize_pharmacy(option.pharmacy)
                        lat, lon = locations[pharmacy]
                        excesses.append(
                            (form, amount, pharmacy, lat, lon, limit, price)
                        )
    return pd.DataFrame(
        excesses,
        columns=['form', 'amount', 'pharmacy', 'lat', 'lon', 'limit', 'price']
    )


def dump_excesses(excesses, locations, coordinates, path='viz/map/data.json'):
    data = []
    for pharmacy, group in excesses.groupby('pharmacy'):
        prices = []
        group = group.sort('difference', ascending=False, inplace=False)
        for _, row in group.iterrows():
            prices.append({
                'form': row.form,
                'amount': row.amount,
                'limit': row.limit,
                'price': row.price,
            })
        lat, lon = locations[pharmacy]
        phone, address = coordinates[pharmacy]
        data.append({
            'pharmacy': pharmacy,
            'lat': lat,
            'lon': lon,
            'phone': phone,
            'address': address,
            'prices': prices
        })
    with open(path, 'w') as dump:
        json.dump(data, dump)
