import arxivpy
import datetime
from itertools import compress
import unidecode
import re
import os
import urllib
import pandas as pd

class Reader(object):
    def __init__(self, detailed=True):
        self.detailed = detailed

    def download_info(self):
        self.articles = arxivpy.query(search_query=['cond-mat.quant-gas'],
                                 start_index=0, max_index=30, sort_by='submittedDate')

        p_ = '../interesting_authors.csv'
        if not os.path.isfile(p_):
            url = "https://www.dropbox.com/s/yismcsi2ti35qse/interesting_authors.csv?dl=1"
            u = urllib.request.urlopen(url)
            data = u.read()
            u.close()
            # Create folder
        #     os.makedirs(os.path.split(p_)[0], exist_ok=True)
            with open(p_, "wb") as f :
                f.write(data)
        authors = pd.read_csv( p_, header=None , squeeze=True)
        self.interesting_authors = authors.squeeze().tolist()

        p_ = '../interesting_keywords.csv'
        if not os.path.isfile(p_):
            url = "https://www.dropbox.com/s/u9pqzmomoa0jgmm/interesting_keywords.csv?dl=1"
            u = urllib.request.urlopen(url)
            data = u.read()
            u.close()
            # Create folder
        #     os.makedirs(os.path.split(p_)[0], exist_ok=True)
            with open(p_, "wb") as f :
                f.write(data)
        keywords = pd.read_csv( p_, header=None , squeeze=True)
        self.interesting_title_keywords = authors.squeeze().tolist()


    def read_arxiv(self):
        # Grab recent articles from the arxiv
        dates = [article.get('publish_date') for article in self.articles]
        last_weekday = dates[0].weekday()
        last_weekday = ['monday','tuesday', 'wednesday', 'thursday', 'friday'][last_weekday]
        date_sel = [date.day==dates[0].day for date in dates]
        new_articles = list(compress(self.articles, date_sel))
        num_new_articles = len(new_articles)

        authors = [unidecode.unidecode(article.get('authors').lower()) for article in new_articles]
        titles = [unidecode.unidecode(article.get('title').lower()) for article in new_articles]

        for i in range(len(new_articles)):
            interest = 0
            for author in self.interesting_authors:
                if re.search(author,authors[i]):
                    interest+=1
            for keyword in self.interesting_title_keywords:
                if re.search(keyword,titles[i]):
                    interest+=1
            new_articles[i]['interest'] = interest

        interesting_new_articles = [article for article in new_articles if article['interest']!=0]
        num_interesting_new_articles = min(len(interesting_new_articles), 4)

        titles_to_say = [unidecode.unidecode(article.get('title').lower()) for article in interesting_new_articles]
        main_authors = [unidecode.unidecode(article.get('main_author').lower()) for article in interesting_new_articles]
        english_listing = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth']

        thing_to_say = str(num_new_articles) + " new articles were uploaded to the archive on " + last_weekday + ", "

        if self.detailed:
            if num_interesting_new_articles:
                thing_to_say += str(num_interesting_new_articles) +" of which you might be interested in."

                for i in range(num_interesting_new_articles):
                    thing_to_say += ' The ' +english_listing[i] + ' article is titled ' + titles_to_say[i] + ". It was written by " + main_authors[i] + " and others."

                thing_to_say += " Unfortunately, I don't know what any of that means. That's all! Check again later."

            else:
                thing_to_say += " I couldn't find any articles that match your interests. Check again later."


        return thing_to_say
