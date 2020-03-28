import pandas as pd
import requests
import os
import glob
from pathlib import Path
from typing import *
from datetime import datetime
import shutil

import pandemics.repo

# Clone JHU repo into current working directory
pandemics.repo.clone_jhu()
recovered = pandemics.repo.jhu_recovered()
confirmed = pandemics.repo.jhu_confirmed()
deaths = pandemics.repo.jhu_deaths()

# Load our world data from the data/world directory
world = []

for csvfile in glob.glob('data/world/*.csv'):
    df = pd.read_csv(csvfile, dtype={
        'cases': 'Int64',
        'new_cases': 'Int64',
        'deaths': 'Int64',
        'serious_and_critical': 'Int64',
        'recovered': 'Int64'
    })
    world.append(df)

# Normalize the JHU data to match our data and how we're doing things

def normalize_jhu_data(df) -> pd.DataFrame:
    # We are just gonna do per country data in this CSV file
    df = df.drop(columns=['Province/State'])
    # Change column names to the ones we use
    df = df.rename(columns={
        'Country/Region': 'country',
        'Lat': 'latitude',
        'Long': 'longitude'
    })

    # Remove duplicate countries
    dup_countries = {
        'Bahamas, The',
        'Congo (Brazzaville)'
    }

    df = df[~df.country.isin(dup_countries)]

    # Change Korea, South to South Koreaa
    df.country = df.country.replace({
        'Korea, South': 'South Korea',
        'US': 'United States',
        'The Bahamas': 'Bahamas',
        'Congo (Kinshasa)': 'Democratic Republic of the Congo',
        'Czechia': 'Czech Republic',
        'Taiwan*': 'Taiwan',
        'Cruise Ship': 'Diamond Princess',
        'Cote d\'Ivoire': 'Ivory Coast'
    })

    # JHU data has a PK of (region, country) so we need to sum up the rows that are dates for each one
    dup = df[df.duplicated(['country'])]
    dup = dup.groupby('country').sum()
    dup = dup.reset_index()
    dup.latitude = 0
    dup.longitude = 0

    # Unique countries
    df = df[~df.duplicated(['country'], keep=False)]
    df = df.append(dup)

    return df

def normalize_our_data(df) -> pd.DataFrame:
    df.country = df.country.replace({
        'Congo Republic': 'Republic of the Congo',
        'DR Congo': 'Democratic Republic of the Congo'
    })
    return df

recovered = normalize_jhu_data(recovered)
confirmed = normalize_jhu_data(confirmed)
deaths = normalize_jhu_data(deaths)

world = [normalize_our_data(df) for df in world]

country1 = set(world[0].country)
country2 = set(recovered.country)
new_countries = country1 - country2
no_new_data = country2 - country1

print('Countries we have that JHU doesn\'t')
print(new_countries)
print('Countries JHU has that we don\'t')
print(no_new_data)

print(f'We have {len(new_countries)} more countries than JHU')
print(f'JHU has {len(no_new_data)} more countries than us')

# The dataframe we we will join onto JHU's data will be the columns country,3/24/20,3/25/20
# 3/24/20 and 3/25/20 will have either recovered, confirmed, or deaths as an integer in them
# construct a dataframe for each days csv file

new_recovered = []
new_confirmed = []
new_deaths = []
common_cols = ['country', 'latitude', 'longitude']

for date,df in zip(['3/24/20', '3/25/20', '3/26/20'], world):
    r = df[common_cols + ['recovered']].rename(columns={
        'recovered': date
    })
    c = df[common_cols + ['cases']].rename(columns={
        'cases': date
    })
    d = df[common_cols + ['deaths']].rename(columns={
        'deaths': date
    })

    new_recovered.append(r)
    new_confirmed.append(c)
    new_deaths.append(d)

def join_data(df, to_join) -> pd.DataFrame:
    for j in to_join:
        df = df.merge(j, how='outer', on='country', suffixes=['_jhu', '_unh'])
        df = df.drop(columns=['latitude_jhu', 'longitude_jhu'])
        df = df.rename(columns={
            'latitude_unh': 'latitude',
            'longitude_unh': 'longitude'
        })
    
    # Rearrange the data so latitude and longitude is at the beginning
    cols = list(df)
    cols.insert(1, cols.pop(cols.index('latitude')))
    cols.insert(2, cols.pop(cols.index('longitude')))
    df = df[cols]

    return df

recovered = join_data(recovered, new_recovered)
confirmed = join_data(confirmed, new_confirmed)
deaths = join_data(deaths, new_deaths)

def take_greatest(df) -> pd.DataFrame:
    to_drop = {col for col in df.columns if col.endswith('_jhu') or col.endswith('_unh')}
    dates = {col.split('_')[0] for col in df.columns if col != 'country'}

    for date in dates:
        df[date] = df.filter(like=date).max(axis=1)
    
    df = df.drop(columns=to_drop)
    # Sort the date columns by their datetime value
    date_cols = sorted(df.columns[3:], key=lambda d: datetime.strptime(d, '%m/%d/%y'))
    # Convert date columns to integer
    df = df.astype({d:'Int64' for d in date_cols})
    df = df[['country', 'latitude', 'longitude'] + date_cols]

    # Make null lat/lons 0s
    df.latitude = df.latitude.fillna(0.0)
    df.longitude = df.longitude.fillna(0.0)

    return df

confirmed = take_greatest(confirmed)
deaths = take_greatest(deaths)
recovered = take_greatest(recovered)

Path('data/time_series').mkdir(exist_ok=True, parents=True)
confirmed.to_csv('data/time_series/global_confirmed.csv')
deaths.to_csv('data/time_series/global_deaths.csv')
recovered.to_csv('data/time_series/global_recovered.csv')



