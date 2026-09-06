# Instrucoes do projeto

- Ambiente recomendado: `.venv` com Python 3.13.
- Execute os comandos a partir da raiz do workspace.
- Use `projeto/capturar_frames.py` para coletar imagens da ESP32-CAM.
- Anote com LabelMe usando as classes definidas em `projeto/utils/config.py`.
- O dataset `yolo/` e externo e serve somente para validacao temporaria.
- Nao use o modelo treinado com 1% do dataset como modelo final.
