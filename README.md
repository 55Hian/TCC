# Controle Autônomo de Inventário

ESP32-CAM, YOLO, MediaPipe e interface web FastAPI.

A documentação do sistema está consolidada em dois manuais:

- [Manual Técnico](docs/MANUAL_TECNICO.md): arquitetura, código, funções, métodos, serviços, rotas e contratos da API.
- [Manual de Uso](docs/MANUAL_DE_USO.md): instalação, configurações, interface, comandos, treinamento e diagnóstico.

Execute a partir da raiz, com o ambiente e os pesos preparados conforme o Manual de Uso:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --port 8000 --workers 1
```

Abra http://localhost:8000. A arquitetura de treino e inferência é escolhida por MODELO_ATIVO em backend/app/core/config.py; alterações exigem reiniciar o processo.
