import json
import urllib
import requests
from bs4 import BeautifulSoup
from src.scheme.scheme import SCHEME
from datetime import datetime


class BaseRequest:
    def __init__(self):
        
        self.URL_BASE = 'http://refor.detran.rj.gov.br/'
        self.URL_WOOK = ''
        self.inputs = {'qtdDoc': 0}
        self.files = list()
        self.current_screen = str()
        self.total_files = str()
        self.processo = str()
        self.idTarefa = str()
        self.cont = int()


    def set_global_variable(self, total_files:int, idTarefa:int, processo:str, instancia=int):
        self.instancia = instancia
        self.total_files = total_files
        self.processo = processo
        self.idTarefa = idTarefa
        URL_1 = 'https://pje.tjba.jus.br/pje'
        URL_2 = 'https://pje2g.tjba.jus.br/pje'
        self.inputs['URL_BASE'] = URL_1 if self.instancia in (1, '1') else URL_2
        self.inputs['domain'] = self.inputs['URL_BASE'].split('br')[0] + 'br'
        self.inputs['processo'] = processo.strip()


    def search_inputs(self, content):
        soup = BeautifulSoup(content, "html.parser")
        try:
            return {
                "cid" :soup.find('input', {'name': 'cid'})['value'],
                "mimes" : soup.find('input', {'name': 'mimes'})['value'],
                "mimesEhSizes" : soup.find('input', {'name': 'mimesEhSizes'})['value'],
                "AjaxRequest" : soup.find('input', {'id': 'commandButtonLoteTipo'})['onclick'].split("containerId':'")[1].split("',")[0],
                "qtdDoc" : soup.find('input', {'id': 'quantidadeProcessoDocumento'})['value'],
                "ViewState": soup.find('input', {'name': 'javax.faces.ViewState'})['value']
            }
        except:
                return {"ViewState": soup.find('input', {'name': 'javax.faces.ViewState'})['value']}

    

    def switch_to_screen(self, screen: str):
            self.current_screen = screen


    def event_expected(self, screen, response):
        data = SCHEME(inputs=self.inputs)[screen]['expected_message']
        soup = BeautifulSoup(response.content, "html.parser")

        if data['not_expected_url'] in response.text and self.current_screen == 'ScheduleRequestForm':
            return self.returnMsg(msg="URl error confirmed", error=True, response=response, forced=False)
        if data['expected_url'] in response.url and data['expected_url'] != "":
            return self.returnMsg(error=False, response=response, forced=False)
        
        if data.get('tag'):
            text_result = soup.find(data['tag'], {data['type']: data['value']})
            if text_result:
                text_result = text_result.text.strip().lower()
                if data['expected_text'] in text_result and data['expected_text'] != "":
                    return self.returnMsg(msg=text_result, error=False, response=response, forced=False)
                for text in data['not_expected']:
                    if text in text_result:
                        return self.returnMsg(msg=text_result, error=True, response=response, forced=False)
            else:
                self.returnMsg(msg=text_result, error=True, response=response, forced=False)
        else:
            return True



    def returnMsg(self, forced:bool, msg=None, error=None, response=None):
        if msg is not None:
            self.files.append({
                            "msg": msg,
                            "error": error,
                            "status_code": response})
        else: 
            return error
        if forced or self.total_files == self.cont: 
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            event = {
                    "event":{  
                    "screen":self.current_screen,
                    "created_at":dt_string,
                    "processo": self.processo,
                    "idTarefa": self.idTarefa,
                    "total_files":self.total_files,
                    "data":self.files
                    }}
            requests.request("POST", url=self.URL_WOOK, json=event, timeout=10)
    
                

    @staticmethod
    def screen_decorator(screen: str):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                if self.current_screen != screen:
                    raise Exception(f"Need to be on {screen} screen: {self.current_screen}")
                return func(self, *args, **kwargs)

            return wrapper
        return decorator


    def find_text(self, num_termo=str, num_anexo=str):
        try:
            js_process = self.open_json()
            js_anexo = self.open_json(json_name="anexo")
            return self.inputs.update({'num_termo': num_termo, 'ipDesc': js_process[num_termo],
                                       "num_anexo": num_anexo, 'ipDescAnexo': js_anexo[num_anexo]})
        except Exception as e:
            ValueError(f'number is not in the json: {e}')
    
    def open_json(self, json_name=None):
        if json_name == "anexo":
            filename = f"itens_anexo_{self.instancia}"
        else:
            filename = f"itens_{self.instancia}"
        with open(f'json_files/{filename}.json') as f:
            return json.load(f)
    

    def add_schedule(self, qtddoc, descDoc):
        return [
            (f'j_id223:{qtddoc}:ordem', '2'),
            (f'j_id223:{qtddoc}:descDoc', descDoc),
            (f'j_id223:{qtddoc}:numeroDoc', ''),
            (f'j_id223:{qtddoc}:tipoDoc', self.inputs['num_anexo']) 
            ]
    
        
    def request(self, method, url, decode:bool, headers=None, payload=None, params=None, files=None):
            try:
                if decode:
                    payload = urllib.parse.urlencode(payload, quote_via=urllib.parse.quote)
                if files != {}: 
                    del headers['Content-Type']
                return self.session.request(method, url=url, params=params,
                                    headers=headers, data=payload, files=files)
            except:
                return "Failed to process the request"

    def update_form(self, payload, headers, descDoc=None):
            scheme = SCHEME(inputs=self.inputs, peticionarUrl=self.peticionarHTML.url)
            payloadUpdate = scheme['GlobalForm']['payload']
            headersUpdate = scheme['GlobalForm']['headers']
            payloadUpdate.update(payload), headersUpdate.update(headers)
            if int(self.inputs['qtdDoc']) > 0:
                payload = [(key, payload[key]) for key in payload]
                payload = payload + self.add_schedule(descDoc=descDoc, qtddoc=self.inputs['qtdDoc'])
            return payloadUpdate, headersUpdate
    

    def find_idProcesso(self, idProcesso, response):
        soup = BeautifulSoup(response.content, 'html.parser')
        if idProcesso == '':
            idProcesso = soup.find('a', {'title': 'Peticionar'})['id'].split(':')[-2]
            return idProcesso
        table = soup.find('tbody', {'id': 'fPP:processosTable:tb'})
        for tr in table.findAll('tr'):
            if idProcesso in tr.td['id']:
                return idProcesso
        

    def find_locator(self, element:str, arquivo=None, files=None, inputs=dict(),
                     username=None, password=None, captcha=None):
        screen = self.current_screen
        datas = SCHEME(inputs=inputs, arquivo=arquivo, files=files, username=username,
                       password=password, captcha=captcha)[screen][element]
        for data in datas:
            if data.get('update_form'):
                data['payload'], data['headers'] = self.update_form(payload=data['payload'], headers=data['headers'], descDoc=arquivo)
            response = self.request(method=data['method'], 
                         url=data['url'], payload=data['payload'], 
                         headers=data['headers'], params=data['params'],
                         decode=data['decode'], files=data['files'])
        return response