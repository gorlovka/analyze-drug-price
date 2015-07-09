#!/usr/bin/env python

import re

import requests

import pandas as pd


def bad_price_format(match):
    price = match.group(1)
    return ', "{}",'.format(price)


def remove_sep(match):
    cell = match.group(0)
    return cell.replace(',', '.')
    

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
            if name == '~':
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
