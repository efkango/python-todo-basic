from sanic import Sanic
from sanic.response import json
import asyncpg
import asyncio

app = Sanic("DatabaseApp")

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'postgres',
    'database': 'local_tests'
}

async def log_action(message):
    await asyncio.sleep(0.1)
    print(f"Log: {message}")

@app.listener('before_server_start')
async def setup_db(app, loop):
    try:
        app.ctx.db_pool = await asyncpg.create_pool(**DB_CONFIG)
        async with app.ctx.db_pool.acquire() as connection:
            await connection.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL
                )
            ''')
        print("✅ Veritabanı bağlantısı başarılı!")
    except Exception as e:
        print(f"❌ Veritabanı hatası: {str(e)}")
        raise e

@app.get("/users")  
async def get_users(request):
    try:
        async with app.ctx.db_pool.acquire() as connection:
            users = await connection.fetch('SELECT * FROM users')
            await log_action("Kullanıcılar listelendi")
            return json([dict(user) for user in users])
    except Exception as e:
        print(f"Get hatası: {str(e)}")
        return json({'error': str(e)}, status=500)

@app.post("/users")  
async def create_user(request):
    try:
        data = request.json
        if not data:
            return json({'error': 'Request body is empty'}, status=400)

        name = data.get('name')
        email = data.get('email')
        
        if not name or not email:
            return json({'error': 'Name and email are required'}, status=400)
        
        async with app.ctx.db_pool.acquire() as connection:
            user = await connection.fetchrow(
                'INSERT INTO users (name, email) VALUES ($1, $2) RETURNING *',
                name, email
            )
            await log_action(f"Yeni kullanıcı oluşturuldu: {name}")
            return json(dict(user))
            
    except Exception as e:
        print(f"Post hatası: {str(e)}")
        return json({'error': str(e)}, status=500)

@app.post("/batch-create")  # Batch endpoint'i
async def batch_create_users(request):
    try:
        data = request.json
        if not data or not isinstance(data, list):
            return json({'error': 'Request body should be an array'}, status=400)

        results = []
        async with app.ctx.db_pool.acquire() as connection:
            tasks = []
            for user_data in data:
                if not user_data.get('name') or not user_data.get('email'):
                    continue
                task = connection.fetchrow(
                    'INSERT INTO users (name, email) VALUES ($1, $2) RETURNING *',
                    user_data['name'], user_data['email']
                )
                tasks.append(task)
            
            if tasks:
                completed = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(completed):
                    if isinstance(result, Exception):
                        results.append({
                            'status': 'error',
                            'error': str(result),
                            'data': data[i]
                        })
                    else:
                        results.append({
                            'status': 'success',
                            'user': dict(result)
                        })
                        await log_action(f"Batch: Kullanıcı oluşturuldu - {data[i]['name']}")

        return json({
            'total': len(results),
            'results': results
        })
            
    except Exception as e:
        print(f"Batch hatası: {str(e)}")
        return json({'error': str(e)}, status=500)

async def cleanup():
    await asyncio.sleep(60) 
    print("Temizlik işlemi başladı...")

@app.listener('after_server_start')
async def start_background_tasks(app, loop):
    app.add_task(cleanup())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)


