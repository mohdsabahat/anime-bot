## DB Migration

1. Auto-Generate revisions
```bash
alembic revision --autogenerate -m "Add Episode langauge column"
```
> Make sure you have below config in alembic `env.py` file for autogenrating migrations

```python
from src.anime_bot.models import UploadedFile, Base
target_metadata = Base.metadata
```

2. Upgrade DB
```bash
alembic upgrade head
```