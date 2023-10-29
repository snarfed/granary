import datetime
from bs4 import BeautifulSoup
import requests

from granary import source

USER_AGENT = 'Granary feed bot - for support contact sarajaksa@sarajaksa.eu'


class ArchiveOfOurOwn(source.Source):
    DOMAIN = 'https://archiveofourown.org'
    URL_BASE = 'https://archiveofourown.org'
    NAME = 'ArchiveOfOurOwn'

    def get_stories_from_single_page(self, html):
        activities_works = []

        soup = BeautifulSoup(html, features='lxml')
        works_elements = soup.find_all(
            lambda tag: tag.name == 'li'
                        and tag.get('class')
                        and len([tag_class for tag_class in tag.get('class') if tag_class.startswith('work')])
        )
        for work in works_elements:
            work_id = work.get('id').split('_')[1]
            chapter_id = 0
            chapters_element_link = work.find('dd', class_='chapters').find('a')
            if chapters_element_link:
                chapter_link_href = chapters_element_link.get('href')
                chapter_id = chapter_link_href.split('/chapters/')[1]
            work_and_chapter_id = f'{work_id}-{chapter_id}'

            date_updated_string = work.find('p', class_='datetime').text
            date_updated = datetime.datetime.strptime(date_updated_string, '%d %b %Y').strftime('%Y-%m-%d')

            author = [author.text for author in work.find_all('a', rel='author')]
            if not len(author):
                author = [work.find('h4').encode_contents().decode().split('<!-- do not cache -->')[1].strip()]

            author = ", ".join(author)

            work_url = f'https://archiveofourown.org/works/{work_id}'
            if chapter_id:
                work_url += f'/chapters/{chapter_id}'

            work_object = {
                'id': work_and_chapter_id,
                'objectType': 'work',
                'verb': 'post',
                'published': date_updated,
                'username': author,
                'content': work.encode_contents().decode(),
                'content_is_html': True,
                'url': work_url,
            }

            activities_works.append({
                'objectType': 'activity',
                'verb': 'post',
                'object': work_object,
            })

        return activities_works

    def get_stories(self, url):
        stories_response = requests.get(url, headers={'User-Agent': USER_AGENT})
        return self.get_stories_from_single_page(stories_response.text)

    def url_to_activities(self, url=None):
        return self.get_stories(url)

