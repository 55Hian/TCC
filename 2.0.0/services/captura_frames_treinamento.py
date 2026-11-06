import cv2
import time
import os
from pathlib import Path

def capturar_frames_da_camera(url_da_camera, qtdFrames):

    base_dir = Path(__file__).resolve().parents[1]
    diretorio_de_salvamento = str(base_dir / "data" / "treinamento")
    os.makedirs(diretorio_de_salvamento, exist_ok=True)
    
    # Inicializa a conexão de vídeo com a câmera
    captura_de_video = cv2.VideoCapture(url_da_camera)

    # Verifica se a conexão com a câmera foi estabelecida corretamente
    if not captura_de_video.isOpened():
        return {'response': f'A conexão com a câmera no endereço {url_da_camera} não pôde ser iniciada.'}

    quantidade_de_frames_salvos = 0
    print(f"Iniciando a captura de {qtdFrames} frames...")

    # O laço continua até que a quantidade desejada de imagens seja atingida
    while quantidade_de_frames_salvos < qtdFrames:
        
        # Lê a imagem atual da câmera
        sucesso_na_leitura, quadro_da_imagem = captura_de_video.read()
        
        # Se houver falha na transmissão da imagem, o código pausa e tenta novamente
        if not sucesso_na_leitura:
            print("response: Falha ao receber a imagem da câmera. Tentando conectar novamente...")
            time.sleep(0.5) 
            continue

        # Define o nome do arquivo de imagem
        nome_do_arquivo_de_imagem = f'imagem_capturada_{quantidade_de_frames_salvos}.jpg'
        
        # Salva o arquivo no disco
        cv2.imwrite(os.path.join(diretorio_de_salvamento, nome_do_arquivo_de_imagem), quadro_da_imagem)
        
        # Atualiza o contador apenas se a imagem foi salva com sucesso
        quantidade_de_frames_salvos += 1
        print(f"Imagem salva: {nome_do_arquivo_de_imagem} ({quantidade_de_frames_salvos} de {qtdFrames})")
        
    # Desconecta da câmera e libera a memória
    captura_de_video.release()
    cv2.destroyAllWindows()

    return {'response': f'Processo concluído. Um total de {quantidade_de_frames_salvos} imagens foram salvas com sucesso.'}


if __name__ == "__main__":
    url_da_camera = "http://192.168.15.59:81/stream"  # Substitua pelo URL da sua câmera
    qtdFrames = 360  # Substitua pela quantidade de frames que deseja capturar
    resultado = capturar_frames_da_camera(url_da_camera, qtdFrames)