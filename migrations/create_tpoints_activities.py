import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.config import Config
from app.models.models import TPointsActivity

async def create_tpoints_activities():
    """Создать T-Points активности в базе данных"""
    config = Config()
    engine = create_async_engine(config.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Список всех активностей
    activities_data = [
        # Социальные активности
        ("repost_social_media", 10, "Репост поста в соц сетях"),
        ("magnet_fridge", 30, "Магнитик на холодильник"),
        ("review_headhunter", 30, "Отзыв на hh.ru"),
        ("social_media_video", 30, "Съемка в роликах для соц сетей"),
        ("merch_photo_video", 30, "Фото и видео с мерчем"),
        
        # Образовательные активности
        ("educational_event_proposal", 50, "Предложение образовательного мероприятия"),
        ("birthday_gift", 80, "Подарок на день рождения"),
        ("teambuilding_proposal", 80, "Предложение вариантов тимбилдингов/корпоративов"),
        ("external_education_participant", 80, "Участие во внешних образовательных мероприятиях как слушатель"),
        ("external_sports_participant", 80, "Участие во внешних спортивных мероприятиях"),
        
        # Продуктивные активности
        ("knowledge_base_fill", 100, "Пополнение базы знаний"),
        ("reviews_digests", 100, "Создание обзоров/дайджестов (книги, фильмы, тд)"),
        ("internal_article", 150, "Написание статьи для внутренней публикации"),
        ("internal_meetup_speaker", 150, "Выступление на внутреннем митапе"),
        ("new_technology_ideas", 200, "Идеи и новые технологии для работы, которые решают проблемы"),
        
        # Высокоуровневые активности
        ("external_education_speaker", 300, "Выступление во внешнем образовательном мероприятии"),
        ("external_article", 300, "Написание статьи для внешней публикации"),
        ("external_case_description", 300, "Описание рабочего кейса для внешней публикации"),
        ("internal_meetup_organizer", 300, "Организация внутреннего митапа и выступление на нем"),
        
        # Системные активности
        ("birthday_bonus", 500, "Подарок ко дню рождения"),
        ("anniversary_bonus", 100, "Юбилейный бонус (100 T-Points за каждый год работы)"),
    ]
    
    async with async_session() as session:
        print("Создание T-Points активностей...")
        
        for name, points, description in activities_data:
            # Проверяем, существует ли уже такая активность
            from sqlalchemy import select
            query = select(TPointsActivity).where(TPointsActivity.name == name)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"⚠️  Активность '{name}' уже существует, пропускаем")
                continue
            
            activity = TPointsActivity(
                name=name,
                points=points,
                description=description,
                is_active=True
            )
            session.add(activity)
            print(f"✅ Создана активность: {description} - {points} T-Points")
        
        await session.commit()
        print("\n🎉 Все T-Points активности созданы!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_tpoints_activities()) 