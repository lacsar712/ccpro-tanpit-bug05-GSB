from config.settings import *  # noqa: F401,F403

# 验收测试用文件型 SQLite（WAL：两线程并发提交时第二个写事务等待行锁后落库，
# 与 PostgreSQL 上的行锁排序行为一致）。需显式给 TEST NAME，
# 否则 Django 默认把 SQLite 测试库建成内存共享缓存，表锁会立即报错。
_TEST_DB = str(BASE_DIR / "test_tanpit.sqlite3")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _TEST_DB,
        "TEST": {"NAME": _TEST_DB},
        "OPTIONS": {"timeout": 30, "init_command": "PRAGMA journal_mode=WAL;"},
    }
}
