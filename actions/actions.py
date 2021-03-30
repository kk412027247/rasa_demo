# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List
import requests
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.forms import FormAction

ENDPOINTS = {
    "base": "https://data.medicare.gov/resource/{}.json",
    "xubh-q36u": {
        "city_query": "?city={}",
        "zip_code_query": "?zip_code={}",
        "id_query": "?provider_id={}"
    },
    "b27b-2uc7": {
        "city_query": "?provider_city={}",
        "zip_code_query": "?provider_zip_code={}",
        "id_query": "?federal_provider_number={}"
    },
    "9wzi-peqs": {
        "city_query": "?city={}",
        "zip_code_query": "?zip={}",
        "id_query": "?provider_number={}"
    }
}


FACILITY_TYPES = {
    "hospital":
        {
            "name": "hospital",
            "resource": "xubh-q36u"
        },
    "nursing_home":
        {
            "name": "nursing home",
            "resource": "b27b-2uc7"
        },
    "home_health":
        {
            "name": "home health agency",
            "resource": "9wzi-peqs"
        }
}

class ActionHelloWorld(Action):

    def name(self) -> Text:
        return "action_hello_world"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Hello World!")

        return []


class ActionFacilitySearch(Action):
    def name(self) -> Text:
        return "action_facility_search"

    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        facility = tracker.get_slot("facility_type")
        location = tracker.get_slot("location")
        address = "3001 Hyde St. San Francisco3"
        print(address)
        dispatcher.utter_message("4Here is the address of the {}:{}".format(facility, location))
        return [SlotSet("address", address)]


def _create_path(base: Text, resource: Text, query: Text, values: Text) -> Text:
    if isinstance(values, list):
        return (base + query).format(
            resource, ', '.join('"{0}"'.format(w) for w in values))
    else:
        return (base + query).format(resource, values)


def _find_facilities(location: Text, resource: Text) -> List[Dict]:
    if str.isdigit(location):
        full_path = _create_path(ENDPOINTS['base'], resource,
                                 ENDPOINTS[resource]['zip_code_query'],
                                 location)
    else:
        full_path = _create_path(ENDPOINTS['base'], resource,
                                 ENDPOINTS[resource]['city_query'],
                                 location.upper())
    results = requests.get(full_path).json()
    return results

def _resolve_name(facility_type, resource) -> Text:
    for key, value in facility_type.items():
        if value.get('resource') == resource:
            return value.get('name')
    return ""

class FacilityForm(FormAction):
    def name(self) -> Text:
        return "facility_form"

    @staticmethod
    def required_slots(tracker: "Tracker") -> List[Text]:
        return ["facility_type", "location"]

    def slot_mappings(self) -> Dict[Text, Any]:
        return {"facility_type": self.from_entity(entity="facility_type",
                                                  intent=["inform", "search_provider"]),
                "location": self.from_entity(entity="location",
                                             intent=["inform", "search_provider"])}

    def submit(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict]:
        location = tracker.get_slot('location')
        facility_type = tracker.get_slot('facility_type')
        results = _find_facilities(location, facility_type)
        button_name = _resolve_name(FACILITY_TYPES, facility_type)
        if len(results) == 0:
            dispatcher.utter_message("Sorry, we could now find a {} in {}".format(button_name, location.title()))
            return []

        buttons = []
        for r in results[:3]:
            if facility_type == FACILITY_TYPES['hospital']['resource']:
                facility_id = r.get('provider_id')
                name = r['hospital_name']
            elif facility_type == FACILITY_TYPES['nursing_home']['resource']:
                facility_id = r['federal_provider_number']
                name = r['provider_name']
            else:
                facility_id = r['provider_number']
                name = r['provider_name']
            payload = "/inform{\"facility_id\":\""+ facility_id + "\"}"
            buttons.append({
                "title":"{}".format(name.title()), "payload":payload})
        if len(buttons) == 1:
            message = "Here is a {} near you:".format(button_name)
        else:
            if button_name == 'home health agency':
                button_name = 'home health agencies'
            message = 'Here are {} {}s near you:'. format(len(buttons), button_name)
        dispatcher.utter_button_message(message, buttons)
        return []


class FindHealthCareAddress(Action):
    def name(self) -> Text:
        return "find_healthcare_address"
    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict]:
        facility_type = tracker.get_slot("facility_type")
        healthcare_id = tracker.get_slot("facility_id")
        full_path = _create_path(ENDPOINTS['base'], facility_type,
                                 ENDPOINTS[facility_type]["id_query"],
                                 healthcare_id)
        results = requests.get(full_path).json()
        if results:
            selected = results[0]
            if facility_type == FACILITY_TYPES['hospital']['resource']:
                address = "{}, {}, {} {}".format(selected['address'].title(),
                                                 selected['city'].title(),
                                                 selected['state'].upper(),
                                                 selected['zip_code'].title())
            elif facility_type == FACILITY_TYPES['nursing_home']['resource']:
                address = "{}, {}, {} {}".format(selected['provider_address'].title(),
                                                 selected['provider_city'].title(),
                                                 selected['provider_state'].upper(),
                                                 selected['provider_zip_code'].title())
            else:
                address = "{}, {}, {} {}".format(selected['address'].title(),
                                                 selected['city'].title(),
                                                 selected['state'].upper(),
                                                 selected['zip_code'].title())
            return [SlotSet("facility_address", address)]
        else:
            print("No address found. Most likely this action was executed "
                  "before the user choose a healthcare facility from the "
                  "provided list. "
                  "If this is a common problem in your dialogue flow,"
                  "using a form instead for this action might be appropriate.")
        return [SlotSet("facility_address", "not found")]

class FindFacilityTypes(Action):
    def name(self) -> Text:
        return "find_facility_types"
    def run(self,
            dispatcher:CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List:
        buttons = []
        for t in FACILITY_TYPES:
            facility_type = FACILITY_TYPES[t]
            payload = "/inform{ \"facility_type\": \"" + facility_type.get("resource") + "\"}"
            buttons.append(
                {"tittle":"{}".format(facility_type.get("name").title()),
                 "payload": payload})
        dispatcher.utter_button_template("utter_greet", buttons, tracker)
        return []
