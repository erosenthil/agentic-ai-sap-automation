"""
SAP OData Agent Component for Langflow
---------------------------------------
A reusable Langflow custom component that connects an AI agent
to a live SAP system via OData REST APIs.

Pattern: LLM extracts intent + parameters → component calls SAP OData → returns structured result

Author: Senthil Subramanian
GitHub: https://github.com/erosenthil/agentic-ai-sap-automation
"""

import requests
import json
from langflow.custom import Component
from langflow.inputs import StrInput, SecretStrInput, MessageTextInput
from langflow.outputs import MessageTextOutput
from langflow.schema import Message


class SAPODataAgentComponent(Component):
    """
    Generic SAP OData Agent Component for Langflow.

    This component allows an AI agent to query a live SAP system
    via OData services. It handles authentication, request construction,
    response parsing, and error handling in a reusable, configurable way.

    Typical use: wire this component after an LLM node that extracts
    intent and entity parameters from user input.
    """

    display_name = "SAP OData Agent"
    description = "Queries a SAP system via OData REST API and returns structured results to the AI agent."
    icon = "database"

    inputs = [
        StrInput(
            name="sap_base_url",
            display_name="SAP Base URL",
            info="Base URL of your SAP system OData endpoint (e.g., https://your-sap-host/sap/opu/odata/sap/)",
            required=True,
        ),
        StrInput(
            name="service_name",
            display_name="OData Service Name",
            info="The SAP OData service name (e.g., API_BUSINESS_PARTNER, MM_PUR_PO_MAINT_V1_SRV)",
            required=True,
        ),
        StrInput(
            name="entity_set",
            display_name="Entity Set",
            info="The OData entity set to query (e.g., A_BusinessPartner, PurchaseOrder)",
            required=True,
        ),
        SecretStrInput(
            name="username",
            display_name="SAP Username",
            info="SAP system username (use environment variable in production)",
            required=True,
        ),
        SecretStrInput(
            name="password",
            display_name="SAP Password",
            info="SAP system password (use environment variable in production)",
            required=True,
        ),
        MessageTextInput(
            name="filter_expression",
            display_name="OData Filter Expression",
            info="OData $filter expression extracted by the LLM (e.g., BusinessPartner eq '1000001')",
            required=False,
        ),
        StrInput(
            name="select_fields",
            display_name="Fields to Select",
            info="Comma-separated list of fields to return (e.g., BusinessPartner,BusinessPartnerName,SearchTerm1)",
            required=False,
        ),
        StrInput(
            name="top",
            display_name="Max Records",
            info="Maximum number of records to return ($top parameter). Default: 10",
            value="10",
            required=False,
        ),
    ]

    outputs = [
        MessageTextOutput(
            name="response",
            display_name="Agent Response",
            method="query_sap_odata",
        )
    ]

    def query_sap_odata(self) -> Message:
        """
        Constructs and executes an OData GET request against a SAP system.
        Returns a structured JSON string for downstream LLM processing.
        """
        try:
            # Build OData URL
            url = f"{self.sap_base_url.rstrip('/')}/{self.service_name}/{self.entity_set}"

            # Build query parameters
            params = {
                "$format": "json",
                "$top": self.top or "10",
            }

            if self.filter_expression:
                params["$filter"] = self.filter_expression

            if self.select_fields:
                params["$select"] = self.select_fields

            # Execute request with basic auth
            # In production: use OAuth2/token-based auth via SAP BTP destination service
            response = requests.get(
                url,
                params=params,
                auth=(self.username, self.password),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30,
                verify=True,  # Set to False only for local dev with self-signed certs
            )

            response.raise_for_status()
            data = response.json()

            # Parse OData response structure
            # SAP OData v2 wraps results in d.results; v4 uses value
            results = (
                data.get("d", {}).get("results", [])
                or data.get("value", [])
                or []
            )

            if not results:
                return Message(text=json.dumps({
                    "status": "success",
                    "message": "No records found matching the given criteria.",
                    "record_count": 0,
                    "data": []
                }))

            # Clean metadata from results (remove __metadata keys)
            clean_results = []
            for record in results:
                clean_record = {k: v for k, v in record.items() if k != "__metadata"}
                clean_results.append(clean_record)

            return Message(text=json.dumps({
                "status": "success",
                "record_count": len(clean_results),
                "entity_set": self.entity_set,
                "data": clean_results
            }, indent=2))

        except requests.exceptions.ConnectionError:
            return Message(text=json.dumps({
                "status": "error",
                "error_type": "connection_error",
                "message": "Could not connect to the SAP system. Check the base URL and network connectivity."
            }))

        except requests.exceptions.Timeout:
            return Message(text=json.dumps({
                "status": "error",
                "error_type": "timeout",
                "message": "SAP OData request timed out after 30 seconds."
            }))

        except requests.exceptions.HTTPError as e:
            return Message(text=json.dumps({
                "status": "error",
                "error_type": "http_error",
                "http_status": response.status_code,
                "message": str(e)
            }))

        except Exception as e:
            return Message(text=json.dumps({
                "status": "error",
                "error_type": "unexpected_error",
                "message": str(e)
            }))
