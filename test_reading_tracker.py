import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import importlib.util

sys.path.insert(0, str(Path(__file__).parent))
importlib_spec = importlib.util.spec_from_file_location(
    "reading_db", 
    str(Path(__file__).parent / "ebook_manager" / "reading" / "database.py")
)
reading_db = importlib.util.module_from_spec(importlib_spec)
sys.modules["reading_db"] = reading_db
importlib_spec.loader.exec_module(reading_db)
ReadingDatabase = reading_db.ReadingDatabase
ReadingPosition = reading_db.ReadingPosition
ReadingGoal = reading_db.ReadingGoal

importlib_spec2 = importlib.util.spec_from_file_location(
    "goal_manager", 
    str(Path(__file__).parent / "ebook_manager" / "reading" / "goal_manager.py")
)
goal_manager = importlib.util.module_from_spec(importlib_spec2)
sys.modules["goal_manager"] = goal_manager
importlib_spec2.loader.exec_module(goal_manager)
GoalManager = goal_manager.GoalManager
GoalType = goal_manager.GoalType
GoalPeriod = goal_manager.GoalPeriod


def test_database():
    print("=" * 60)
    print("测试数据库模块")
    print("=" * 60)
    
    test_db_path = os.path.join(Path.home(), ".ebook_reader_tracker", "test_reading.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = ReadingDatabase(test_db_path)
    print("✅ 数据库初始化成功")
    
    book_id = db.add_book(
        file_path="/test/book1.epub",
        title="测试书籍",
        author="测试作者",
        file_format="epub",
        total_pages=300,
        total_words=100000,
        total_chapters=20
    )
    print(f"✅ 添加书籍成功，ID: {book_id}")
    
    position = ReadingPosition(
        book_id=book_id,
        file_path="/test/book1.epub",
        file_format="epub",
        chapter="第一章",
        chapter_index=0,
        paragraph_id="p_0_5",
        paragraph_index=5,
        percentage=0.1,
        word_count=10000
    )
    pos_id = db.save_position(position)
    print(f"✅ 保存位置成功，ID: {pos_id}")
    
    saved_pos = db.get_position(book_id)
    assert saved_pos is not None
    assert saved_pos.chapter == "第一章"
    assert saved_pos.percentage == 0.1
    print("✅ 获取位置成功")
    
    session_id = db.start_session(book_id)
    print(f"✅ 开始阅读会话，ID: {session_id}")
    
    db.add_record(session_id, book_id, "page_turn", {"page": 10})
    print("✅ 添加阅读记录成功")
    
    db.add_activity_event(session_id, "key_press", {"key": "PageDown"})
    print("✅ 添加活动事件成功")
    
    session = db.end_session(session_id, effective_duration=3600, pages_read=50, words_read=15000)
    assert session is not None
    assert session.effective_duration == 3600
    print("✅ 结束会话成功")
    
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    stats = db.get_reading_statistics(start_date, end_date)
    assert stats['total_minutes'] >= 60
    assert stats['total_pages'] == 50
    print(f"✅ 统计查询成功: {stats['total_hours']}小时, {stats['total_pages']}页")
    
    goal = ReadingGoal(
        goal_type=GoalType.BOOKS_FINISHED,
        target_value=5,
        start_date=datetime.now().strftime('%Y-%m-%d'),
        end_date=(datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
        description="本月读完5本书"
    )
    goal_id = db.add_goal(goal)
    print(f"✅ 添加阅读目标成功，ID: {goal_id}")
    
    goals = db.get_active_goals()
    assert len(goals) == 1
    print(f"✅ 获取目标成功，共{len(goals)}个活跃目标")
    
    csv_path = os.path.join(Path.home(), ".ebook_reader_tracker", "test_export.csv")
    db.export_to_csv(start_date, end_date, csv_path)
    assert os.path.exists(csv_path)
    print(f"✅ CSV导出成功: {csv_path}")
    
    book_progress = db.get_book_progress(book_id)
    print(f"✅ 书籍进度: {book_progress}")
    
    print("\n🎉 数据库模块测试通过!")
    return True


def test_goal_manager():
    print("\n" + "=" * 60)
    print("测试目标管理模块")
    print("=" * 60)
    
    test_db_path = os.path.join(Path.home(), ".ebook_reader_tracker", "test_goal.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = ReadingDatabase(test_db_path)
    goal_manager = GoalManager(db)
    
    book_id = db.add_book(
        file_path="/test/book1.epub",
        title="测试书籍",
        author="测试作者",
        file_format="epub",
        total_pages=300,
        total_words=100000
    )
    
    session_id = db.start_session(book_id)
    db.end_session(session_id, effective_duration=7200, pages_read=100, words_read=30000)
    
    goal_id = goal_manager.create_goal(
        goal_type=GoalType.READING_MINUTES,
        target_value=600,
        period=GoalPeriod.WEEKLY,
        description="每周阅读600分钟"
    )
    print(f"✅ 创建目标成功，ID: {goal_id}")
    
    progress = goal_manager.get_goal_progress(goal_id)
    assert progress is not None
    print(f"✅ 目标进度: {progress.current_value}/{progress.target_value} ({progress.percentage:.1f}%)")
    
    goals_progress = goal_manager.get_all_goals_progress()
    print(f"✅ 所有目标进度: {len(goals_progress)}个")
    for gp in goals_progress:
        print(f"   - {gp.description}: {gp.current_value}/{gp.target_value}")
    
    summary = goal_manager.get_goal_summary()
    print(f"✅ 目标摘要: {summary}")
    
    templates = goal_manager.get_goal_templates()
    assert len(templates) == 6
    print(f"✅ 目标模板: {len(templates)}个")
    
    for t in templates:
        print(f"  - {t['name']}: {t['default_target']} {t['default_period']}")
    
    print("\n🎉 目标管理模块测试通过!")
    return True


def main():
    try:
        test_database()
        test_goal_manager()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
        
        print("\n📁 测试文件位置:")
        print(f"   数据库: {Path.home()}/.ebook_reader_tracker/")
        print(f"   图表: {Path.home()}/.ebook_reader_tracker/charts/")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
