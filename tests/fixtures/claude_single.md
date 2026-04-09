**Human:** I want to build a REST API for a task management app. It needs user auth, tasks CRUD, and team support.

**Assistant:** Great project! Let's use FastAPI for the framework — it gives us automatic OpenAPI docs and async support out of the box.

For the stack I'd suggest:
- Language: Python 3.11+
- Framework: FastAPI
- Database: PostgreSQL
- Auth: JWT tokens
- Testing: pytest

**Human:** Let's use JWT for auth, stateless is important. It must run offline and cannot call any external analytics services.

**Assistant:** Agreed — JWT is the right call for a stateless API. Here are the next steps:

1. Set up FastAPI project scaffold
2. Implement JWT auth middleware
3. Define PostgreSQL schema
4. Write unit tests for auth
5. Add team membership endpoints

Open question: Which ORM should we use — SQLAlchemy vs Tortoise ORM?

**Human:** Mobile app is out of scope for v1. Let's keep it API only.
