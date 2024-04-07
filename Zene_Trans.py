from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6 import QtGui
from PIL import Image, ImageDraw, ImageFont, ImageQt
from concurrent.futures import ThreadPoolExecutor
from winocr import recognize_pil_sync
from deep_translator import GoogleTranslator
from wscreenshot import Screenshot
import cv2
import json

class OverlayThread(QThread):
    updated = pyqtSignal(QPixmap)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    
    def run(self):
        def grab_specific_game_windows(window_title):
            game_window = Screenshot(window_title)
            pil_color_converted = cv2.cvtColor(game_window.screenshot(), cv2.COLOR_BGR2RGB)
            return pil_color_converted

        def get_texts():
            text_list =[]
            for text_data in collect_data["lines"]:
                text_list.append(text_data["text"])
            return text_list
        
        def get_text_positions():
            position_list = []
            for text_data in collect_data["lines"]:
                for bounding_rect in text_data["words"][0:1]:
                    x = int(bounding_rect["bounding_rect"]["x"])
                    y = int(bounding_rect["bounding_rect"]["y"])
                    position_list.append((x, y))
            return position_list
                    
        def translate(text):
            translate_config = json.loads(open('translate_config.json').read())
            proxy = translate_config["proxy"]
            lang_target = translate_config["lang_target"]
            proxies = {
                "https": proxy,
                "http": proxy
            }
            
            trans_set = GoogleTranslator(source = 'auto', target=lang_target, proxies = proxies)
            translated_texts = (f'{trans_set.translate(text)}')
            return translated_texts
        
        while self.running:
            
            config = json.loads(open('config.json').read())
            window_title = config["window"]
            font = config["font"]
            ocr_lang = config["ocr_lang"]
            
            pil_img = Image.fromarray(grab_specific_game_windows(window_title))
            width, height = pil_img.size
            transparent_img = Image.new('RGBA', (width, height), (2555, 255, 255, 0))
            myFont = ImageFont.truetype(font, 20)
            draw = ImageDraw.Draw(transparent_img)
            data = json.dumps(recognize_pil_sync(pil_img, ocr_lang))
            collect_data = json.loads(data)
            
            with ThreadPoolExecutor(max_workers = len(get_texts()) + 1) as excutor:
                result = list(excutor.map(translate,get_texts()))
                for text, position in zip(result, get_text_positions()):
                    left, top, right, bottom = draw.textbbox(position, text, font=myFont)
                    draw.rectangle((left-5, top-5, right+5, bottom+5), fill="black")
                    draw.text(position, text, font=myFont, fill="white")
                    
            qimage = ImageQt.ImageQt(transparent_img)
            
            pixmap = QtGui.QPixmap.fromImage(qimage)
            painter = QPainter(pixmap)
            painter.end()
            self.updated.emit(pixmap)
            QThread.msleep(250)
            
class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.pixmap = None
        self.show()
        
    def update_overlay(self, pixmap):
        self.pixmap = pixmap
        self.resize(self.pixmap.size())
        self.update()
        
    def paintEvent(self, event):
        if self.pixmap:
            painter = QPainter(self)
            painter.drawPixmap(self.rect(), self.pixmap)
            
if __name__ == '__main__':
    app = QApplication([])
    overlay = OverlayWindow()
    thread = OverlayThread()
    thread.updated.connect(overlay.update_overlay)
    thread.start()
    app.exec()
            