# Instrucoes do projeto

- Ambiente recomendado: `.venv` com Python 3.13.
- Execute os comandos a partir da raiz do workspace.
- Interface web: `uvicorn main:app --app-dir backend\app --port 8000`, depois abrir http://localhost:8000.
- Use `backend\app\capturar_frames.py` (ou a aba Dataset da interface) para coletar imagens da ESP32-CAM.
- Anote com LabelMe usando as classes definidas em `backend\app\core\config.py`.
- O dataset `data\external_validation\` e externo (nao versionado) e serve somente para validacao temporaria.
- Nao use o modelo treinado com 1% do dataset como modelo final.
- Mantenha os 4 modelos-base em `models\pretrained\` (ainda em avaliacao comparativa).
