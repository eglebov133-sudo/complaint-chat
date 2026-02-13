"""
Сервис интеграции с DaData API
Подсказки для организаций (по ИНН/названию) и адресов
Бесплатно до 10,000 запросов в день
"""
import requests
from typing import Optional, List, Dict
from config import Config


class DaDataService:
    """Сервис для работы с DaData API"""
    
    def __init__(self):
        self.api_key = Config.DADATA_API_KEY
        self.base_url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs"
        
    def _make_request(self, endpoint: str, query: str, count: int = 5) -> Optional[List[Dict]]:
        """Отправка запроса к DaData API"""
        if not self.api_key:
            print("DaData API: No API key configured")
            return None
            
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self.api_key}"
        }
        
        payload = {
            "query": query,
            "count": count
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/{endpoint}",
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if not response.ok:
                print(f"DaData API Error: {response.status_code} - {response.text[:200]}")
                return None
                
            data = response.json()
            return data.get("suggestions", [])
            
        except Exception as e:
            print(f"DaData API Error: {e}")
            return None
    
    def suggest_company(self, query: str, count: int = 5) -> List[Dict]:
        """
        Поиск организаций по названию, ИНН, ОГРН
        
        Returns:
            List of companies with structured location data for jurisdiction
        """
        suggestions = self._make_request("suggest/party", query, count)
        
        if not suggestions:
            return []
        
        result = []
        for s in suggestions:
            data = s.get("data", {})
            address = data.get("address", {})
            address_data = address.get("data", {}) or {}  # Структурированные данные адреса
            management = data.get("management", {})
            
            # Извлекаем структурированную информацию о местоположении
            region = address_data.get("region_with_type", "") or address_data.get("region", "")
            city = address_data.get("city_with_type", "") or address_data.get("city", "")
            city_district = address_data.get("city_district_with_type", "") or address_data.get("city_district", "")
            settlement = address_data.get("settlement_with_type", "") or address_data.get("settlement", "")
            area = address_data.get("area_with_type", "") or address_data.get("area", "")  # Район области
            
            result.append({
                "name": s.get("value", ""),
                "inn": data.get("inn", ""),
                "ogrn": data.get("ogrn", ""),
                "kpp": data.get("kpp", ""),
                "address": address.get("value", ""),
                # Структурированные данные для подведомственности
                "region": region,  # Регион (область, республика, край)
                "city": city,  # Город
                "city_district": city_district,  # Район города (для крупных городов)
                "area": area,  # Район области (для сельской местности)
                "settlement": settlement,  # Населённый пункт
                "type": data.get("type", ""),  # LEGAL или INDIVIDUAL
                "status": data.get("state", {}).get("status", ""),
                "director": management.get("name", ""),
                "director_post": management.get("post", "")
            })
        
        return result
    
    def find_company_by_inn(self, inn: str) -> Optional[Dict]:
        """
        Найти компанию по точному ИНН
        """
        suggestions = self._make_request("findById/party", inn, 1)
        
        if not suggestions:
            return None
        
        s = suggestions[0]
        data = s.get("data", {})
        address = data.get("address", {})
        management = data.get("management", {})
        
        return {
            "name": s.get("value", ""),
            "inn": data.get("inn", ""),
            "ogrn": data.get("ogrn", ""),
            "kpp": data.get("kpp", ""),
            "address": address.get("value", ""),
            "type": data.get("type", ""),
            "status": data.get("state", {}).get("status", ""),
            "director": management.get("name", ""),
            "director_post": management.get("post", "")
        }
    
    def suggest_address(self, query: str, count: int = 5) -> List[Dict]:
        """
        Подсказки адресов
        
        Returns:
            List of addresses with fields:
            - value: полный адрес
            - data.postal_code: индекс
            - data.region: регион
            - data.city: город
            - data.street: улица
            - data.house: дом
        """
        suggestions = self._make_request("suggest/address", query, count)
        
        if not suggestions:
            return []
        
        result = []
        for s in suggestions:
            data = s.get("data", {})
            
            result.append({
                "value": s.get("value", ""),
                "postal_code": data.get("postal_code", ""),
                "region": data.get("region", ""),
                "city": data.get("city", ""),
                "street": data.get("street", ""),
                "house": data.get("house", ""),
                "flat": data.get("flat", "")
            })
        
        return result
    
    def suggest_fio(self, query: str, count: int = 5) -> List[Dict]:
        """
        Подсказки ФИО
        """
        suggestions = self._make_request("suggest/fio", query, count)
        
        if not suggestions:
            return []
        
        result = []
        for s in suggestions:
            data = s.get("data", {})
            result.append({
                "value": s.get("value", ""),
                "surname": data.get("surname", ""),
                "name": data.get("name", ""),
                "patronymic": data.get("patronymic", ""),
                "gender": data.get("gender", "")
            })
        
        return result


# Singleton instance
dadata_service = DaDataService()
