"""Tokkobroker API placeholder helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

SAMPLE_TOKKOBROKER_PROPERTY: Dict[str, Any] = json.loads(
    """
    {
      "status": "Available",
      "operations": [
        {
          "price": "USD 100.000",
          "type": "Venta"
        }
      ],
      "is_default_picture": false,
      "status_id": 2,
      "link": "https://ficha-info-888.sandbox.tokkobroker.com/p/b2e1c6f4ea6a4f07915fb02b90c81e46",
      "address": "Riobamba 550  9E",
      "id": 319,
      "ref_code": "IHO0319",
      "picture_url": "https://static.tokkobroker.com/thumbs/dev_319_5158450034695142716368961992736452230963764899504231760652072396770929_thumb.jpg",
      "location": "Balvanera",
      "type": "Casa",
      "image_files": [
        {
          "files": [
            {
              "in_web": false,
              "description_text": null,
              "alt": "Click para descargar",
              "id": "4",
              "size": 183504,
              "name": "PDF PRUEBA FER.pdf",
              "url": "/multiuploader/show/4/?type=file",
              "thumbnail_url": "",
              "delete_type": "POST",
              "icon": "icon-pdf",
              "type": "pdf",
              "delete_url": "/multiuploader/delete/4/?type=file"
            },
            {
              "in_web": false,
              "description_text": null,
              "alt": "Click para descargar",
              "id": "5",
              "size": 154975,
              "name": "tabla.pdf",
              "url": "/multiuploader/show/5/?type=file",
              "thumbnail_url": "",
              "delete_type": "POST",
              "icon": "icon-pdf",
              "type": "pdf",
              "delete_url": "/multiuploader/delete/5/?type=file"
            }
          ],
          "property_id": 319
        }
      ],
      "files": [
        {
          "files": [
            {
              "in_web": false,
              "description_text": null,
              "alt": "Click para descargar",
              "id": "4",
              "size": 183504,
              "name": "PDF PRUEBA FER.pdf",
              "url": "/multiuploader/show/4/?type=file",
              "thumbnail_url": "",
              "delete_type": "POST",
              "icon": "icon-pdf",
              "type": "pdf",
              "delete_url": "/multiuploader/delete/4/?type=file"
            },
            {
              "in_web": false,
              "description_text": null,
              "alt": "Click para descargar",
              "id": "5",
              "size": 154975,
              "name": "tabla.pdf",
              "url": "/multiuploader/show/5/?type=file",
              "thumbnail_url": "",
              "delete_type": "POST",
              "icon": "icon-pdf",
              "type": "pdf",
              "delete_url": "/multiuploader/delete/5/?type=file"
            }
          ],
          "property_id": 319
        }
      ],
      "quick_data": {
        "web_property_url": "http://TokkoTiger.com.ar/p/319-prop",
        "can_edit": true,
        "company_web": "http://tokkotiger.com.ar",
        "hoggax_data": null,
        "edited": false,
        "favourite": false,
        "is_web_configured": true,
        "data": {
          "operations": {
            "Sale": [
              "USD 100.000"
            ]
          },
          "status": 2,
          "reference": "IHO0319",
          "geolocation": {
            "lat": 0,
            "lng": 0
          },
          "basic_info": [
            {
              "name": "Ambientes",
              "value": 6
            },
            {
              "name": "Dormitorios",
              "value": 3
            },
            {
              "name": "Ba\u00f1o",
              "value": 1
            },
            {
              "name": "Toilette",
              "value": 1
            },
            {
              "name": "Cochera",
              "value": 1
            },
            {
              "name": "Antig\u00fcedad",
              "value": "A estrenar"
            }
          ],
          "rooms": [
            "Comedor",
            "Lavadero"
          ],
          "measurement": [
            {
              "name": "Superficie",
              "value": "180.00 m\u00b2"
            }
          ],
          "id": 319,
          "occupation": [],
          "attributes_list": [
            {
              "attr": "room_amount",
              "value": "6 ambientes",
              "icon": "icon-ambientes"
            },
            {
              "attr": "suite_amount",
              "value": "3 dormitorios",
              "icon": "icon-dormitorios"
            },
            {
              "attr": "bathroom_amount",
              "value": "1 ba\u00f1o",
              "icon": "icon-banos"
            },
            {
              "attr": "toilet_amount",
              "value": "1 toilette",
              "icon": "icon-toilletes"
            },
            {
              "attr": "parking_lot_amount",
              "value": "1 cochera",
              "icon": "icon-cochera"
            },
            {
              "attr": "age",
              "value": "A estrenar",
              "icon": "icon-reloj"
            }
          ],
          "similar_searches": [
            {
              "currency": "USD",
              "operation": "Venta",
              "search": {
                "price_to": 114999,
                "current_localization_type": "division",
                "state_filters": [],
                "only_available": "checked",
                "current_localization_id": "24676",
                "without_custom_tags": [],
                "without_tags": [],
                "currency": "USD",
                "with_custom_tags": [],
                "division_filters": [],
                "filters": [
                  [
                    "age",
                    ">",
                    "-1"
                  ]
                ],
                "with_tags": [],
                "only_reserved": "checked",
                "only_not_available": "checked",
                "price_from": 75000,
                "only_to_be_cotized": "checked",
                "operation_types": [
                  1
                ],
                "property_types": [
                  3
                ]
              }
            }
          ],
          "pictures": {
            "images": [
              "https://static.tokkobroker.com/pictures/dev_319_4723665168838986325130159213392916772639404031813839106281859741235224.jpg",
              "https://static.tokkobroker.com/pictures/dev_319_6727922709136842048038832498804463848819401512772729354960607904782081.jpg",
              "https://static.tokkobroker.com/pictures/dev_319_5351296924053398547876657039888179056585001224069929757641412587183828.jpg"
            ],
            "blueprints": [
              "https://static.tokkobroker.com/pictures/dev_319_5425477817782883866788440024532430738644084452769706560386065918677712.jpg"
            ],
            "front_cover_image": {
              "url": "https://static.tokkobroker.com/pictures/dev_319_5158450034695142716368961992736452230963764899504231760652072396770929.jpg",
              "is_blueprint": false
            }
          },
          "operation_info": null,
          "branch": "Nu\u00f1ez Ofi",
          "location": "Balvanera  | Capital Federal | Argentina",
          "videos": {
            "360": [],
            "normal": []
          },
          "producer_user": {
            "image": "",
            "company": {
              "logo": "https://static.tokkobroker.com/static/img/nologo2.png",
              "name": "Inmobiliaria devs"
            },
            "id": 1,
            "name": "Admin Admin"
          },
          "internal_info": {
            "information": {
              "key_location": "Desconocido",
              "cotization_users": [],
              "producer_commission": null,
              "maintenance_user": null,
              "key_location_reference": null
            },
            "internal_comments": "probando visualizaci\u00f3n",
            "propietaries": [
              {
                "id": 208,
                "name": "Maria Fernandez"
              }
            ]
          },
          "type": "Casa",
          "additionals": [
            "Apto mascotas"
          ],
          "development": {
            "description": "",
            "videos": {
              "360": [],
              "normal": []
            },
            "deadline": null,
            "users_in_charge": [
              {
                "id": 1,
                "name": "Admin Admin"
              }
            ],
            "id": 2,
            "developer": {
              "id": 208,
              "name": "Maria Fernandez"
            },
            "web": "http://TokkoTiger.com.ar/d/2-dev",
            "name": "El dorado ",
            "pictures": {
              "images": [],
              "blueprints": [],
              "front_cover_image": null
            },
            "internal_comments": "",
            "construction_status": "Desconocido",
            "excel_extra_data": []
          },
          "owner_name": "Maria Fernandez",
          "temporary": null,
          "description": "<p>Esto es una prueba de Fer\u00a0</p><p><br></p><p><br></p><p>xxxxxxxxxxx</p><p><br></p><p>xxxxxxx</p>",
          "has_edition": false,
          "operation_block_data": [],
          "address": "Riobamba 550  9E",
          "services": [
            "Agua Corriente",
            "Gas Natural",
            "Internet",
            "Electricidad",
            "Pavimento",
            "Cable"
          ],
          "chat_entre_colegas": {
            "image": "https://backend-888.sandbox.tokkobroker.com/static/img/user.png",
            "company": {
              "logo": "https://static.tokkobroker.com/static/img/nologo2.png",
              "name": "Inmobiliaria devs",
              "id": 5
            },
            "id": 1,
            "name": "Admin Admin"
          },
          "network_share": 50,
          "is_denounced": false,
          "url": "/property/319/",
          "created_at": "18-07-2024",
          "owner_id": 208,
          "is_from_network": false
        },
        "active": true
      },
      "quick_sents": {
        "total_sents": 0,
        "sent_history": []
      },
      "reservations": []
    }
    """
)


def fetch_tokkobroker_properties() -> List[Dict[str, Any]]:
    """Return Tokkobroker property payloads.

    This placeholder returns a canned response until the real integration is
    implemented.
    """

    return [SAMPLE_TOKKOBROKER_PROPERTY]


__all__ = ["fetch_tokkobroker_properties", "SAMPLE_TOKKOBROKER_PROPERTY"]
