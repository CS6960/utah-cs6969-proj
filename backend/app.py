import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def hello():
    return {'message': 'Hello, World!'}


@app.get('/api/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    uvicorn.run('app:app', host='0.0.0.0', port=port, reload=True)
