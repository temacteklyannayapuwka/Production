from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Category, News


DEMO_NEWS = [
    ('obshchestvo', 'Общество', 'Новый жилой комплекс на 500 квартир введут в эксплуатацию до конца года', 'feature.jpg'),
    ('kultura', 'Культура', 'Открытие выставки художников Северного Кавказа состоится в пятницу', 'news-1.jpg'),
    ('sport', 'Спорт', 'Ставропольские спортсмены завоевали медали на всероссийском турнире', 'news-2.jpg'),
    ('zdorove', 'Здоровье', 'В крае открыли новый медицинский центр для детей и взрослых', 'news-3.jpg'),
    ('obshchestvo', 'Общество', 'В Пятигорске благоустроят ещё три общественных пространства', 'news-4.jpg'),
    ('politika', 'Политика', 'Губернатор обсудил с главами округов планы развития территорий', 'news-1.jpg'),
    ('proisshestviya', 'Происшествия', 'На трассе М-29 ликвидировали крупный затор после ДТП', 'feature.jpg'),
    ('politika', 'Политика', 'В крае утвердили дополнительные меры поддержки малого бизнеса', 'news-2.jpg'),
    ('ekonomika', 'Экономика', 'Аграрии Ставрополья собрали рекордный урожай зерновых', 'news-3.jpg'),
    ('obshchestvo', 'Общество', 'К началу учебного года в регионе откроют новые школы и детский сад', 'news-4.jpg'),
    ('obshchestvo', 'Общество', 'В Пятигорске завершили ремонт важного участка дороги', 'news-1.jpg'),
    ('obshchestvo', 'Общество', 'На Ставрополье стартовала программа поддержки молодых семей', 'news-2.jpg'),
    ('zdorove', 'Здоровье', 'График работы поликлиник изменится в праздничные дни', 'news-3.jpg'),
    ('obshchestvo', 'Общество', 'Новый маршрут свяжет отдалённые районы краевой столицы', 'news-4.jpg'),
    ('obshchestvo', 'Общество', 'Школьники региона отправились на всероссийский форум', 'feature.jpg'),
    ('ekonomika', 'Экономика', 'Фермеры края представили урожай на большой выставке', 'news-1.jpg'),
    ('proisshestviya', 'Происшествия', 'Спасатели предупредили жителей о сильном ветре', 'news-2.jpg'),
    ('kultura', 'Культура', 'В центре Ставрополя пройдёт вечерний концерт', 'news-3.jpg'),
    ('sport', 'Спорт', 'В регионе открыли современную спортивную площадку', 'news-4.jpg'),
    ('obshchestvo', 'Общество', 'Эксперты рассказали, как выбрать школьные товары', 'feature.jpg'),
    ('ekonomika', 'Экономика', 'На рынках края снизились цены на сезонные овощи', 'news-1.jpg'),
    ('kultura', 'Культура', 'Культурные площадки подготовили программу на выходные', 'news-2.jpg'),
]


class Command(BaseCommand):
    help = 'Создаёт локальные демонстрационные новости с изображениями для главной страницы.'

    def handle(self, *args, **options):
        now = timezone.now()
        image_dir = Path(settings.BASE_DIR) / 'static' / 'demo-news'
        categories = {}

        for order, (slug, name, _, _) in enumerate(DEMO_NEWS, start=1):
            category, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'order': order, 'is_active': True},
            )
            categories[slug] = category

        created = 0
        for index, (category_slug, _, title, image_name) in enumerate(DEMO_NEWS, start=1):
            news, was_created = News.objects.get_or_create(
                slug=f'demo-{index}',
                defaults={
                    'title': title,
                    'content': f'<p>{title}</p><p>Демонстрационный материал для локальной проверки нового дизайна.</p>',
                    'excerpt': 'Демонстрационный материал для локальной проверки нового дизайна.',
                    'category': categories[category_slug],
                    'is_published': True,
                    'date_start': now - timedelta(minutes=index * 12),
                    'views': 25000 - index * 750,
                },
            )
            if was_created:
                image_path = image_dir / image_name
                with image_path.open('rb') as image_file:
                    news.main_photo.save(image_name, File(image_file), save=True)
                created += 1

        self.stdout.write(self.style.SUCCESS(f'Готово: создано {created} демо-новостей.'))
