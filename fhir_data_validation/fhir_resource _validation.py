import json  
import logging
import os
from datetime import datetime  
import pytz
import azure.functions as func  
from fhir.resources.bundle import Bundle  
from fhir.resources.patient import Patient  
from fhir.resources.condition import Condition  
from fhir.resources.encounter import Encounter  
from fhir.resources.appointment import Appointment  
from fhir.resources.observation import Observation  
from fhir.resources.servicerequest import ServiceRequest  
from fhir.resources.medicationrequest import MedicationRequest  
from fhir.resources.allergyintolerance import AllergyIntolerance 
from pydantic import ValidationError, BaseModel
from typing import List, Tuple
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


fhir_resource_validation_blueprint = func.Blueprint()


# Function to ensure datetime fields are timezone aware
def ensure_timezone_aware(dt_str):  
    try:  
        dt = datetime.fromisoformat(dt_str)  
        if dt.tzinfo is None:  
            dt = dt.replace(tzinfo=pytz.UTC)  
        return dt.isoformat()  
    except ValueError:  
        return dt_str

# Function to fetch the required and optional fields for each resourceType
def get_required_optional_fields(resource_class: BaseModel) -> Tuple[List[str], List[str]]:  
    required_fields = []  
    optional_fields = []  
  
    for field_name, field in resource_class.__fields__.items():  
        if field.default is None and field.default_factory is None:  
            required_fields.append(field_name)  
        else:  
            optional_fields.append(field_name)  
  
    return required_fields, optional_fields  

# Function to fetch all the fields for each resourceType present in the generated data
def extract_all_fields(data, parent_key=''):  
    fields = []  
    
    if isinstance(data, dict):  
        for key, value in data.items():  
            new_key = f"{parent_key}.{key}" if parent_key else key  
            fields.append(new_key)  
            fields.extend(extract_all_fields(value, new_key))  
    elif isinstance(data, list):  
        for index, item in enumerate(data):  
            new_key = f"{parent_key}[{index}]"
            fields.append(new_key) 
            fields.extend(extract_all_fields(item, new_key))  
    else:  
        if parent_key:  
            fields.append(parent_key) 
    
    return fields

# Function to check if fields in the resource exists within a nested dictionary structure
def check_field_presence(field, data):  
    parts = field.split('.')     # Split into a list of parts
    current = data  
    
    # Iterates through each part
    for part in parts:
        # Check if the current part exists as a key within that dictionary
        if isinstance(current, dict) and part in current:  
            current = current[part]  
        # Check if the current part exists as a key within that dictionary  
        elif isinstance(current, list):  
            try:  
                index = int(part.strip('[]'))  
                current = current[index]  
            except:  
                return False  
        else:  
            return False  
    return True

# Function to validate individual FHIR resources
def validate_individual_fhir_resource(resource_type, resource_data):
    original_resource_data = json.loads(json.dumps(resource_data))        # Store the original resource data

    try:
        # Adjust the resource data for known issues
        if resource_type == "Encounter":
            # Ensure 'class' is a list  
            if 'class' in resource_data and not isinstance(resource_data['class'], list):  
                resource_data['class'] = [resource_data['class']]
            # Remove 'period' field  
            if 'period' in resource_data:  
                del resource_data['period']
            # Remove 'participant' field  
            if 'participant' in resource_data:  
                del resource_data['participant']  
            # Remove 'diagnosis' field  
            if 'diagnosis' in resource_data:  
                del resource_data['diagnosis']
        
        if resource_type == "Appointment":
            # Ensure 'patientInstruction' is a list  
            if 'patientInstruction' in resource_data and not isinstance(resource_data['patientInstruction'], list):  
                resource_data['patientInstruction'] = [resource_data['patientInstruction']]
            # Handle 'patientInstruction' JSON validation  
            if 'patientInstruction' in resource_data:  
                for i, instruction in enumerate(resource_data['patientInstruction']):  
                    try:  
                        # Attempt to parse as JSON, if it fails, remove the instruction  
                        json.loads(instruction)  
                    except json.JSONDecodeError:  
                        del resource_data['patientInstruction'][i] 
            # Remove 'comment' field 
            if 'comment' in resource_data:  
                del resource_data['comment']
                
        if resource_type == "ServiceRequest":
            # Convert the datetime string to a timezone-aware datetime string if necessary
            if 'occurrenceDateTime' in resource_data:
                resource_data['occurrenceDateTime'] = ensure_timezone_aware(resource_data['occurrenceDateTime']) 
            if 'occurrenceTiming' in resource_data:
                if 'event' in resource_data['occurrenceTiming']:  
                    resource_data['occurrenceTiming']['event'] = [  
                        ensure_timezone_aware(event['effectiveDateTime']) if isinstance(event, dict) and 'effectiveDateTime' in event else event  
                        for event in resource_data['occurrenceTiming']['event']  
                    ]
                if 'repeat' in resource_data['occurrenceTiming']:  
                    if 'boundsPeriod' in resource_data['occurrenceTiming']['repeat']:  
                        bounds_period = resource_data['occurrenceTiming']['repeat']['boundsPeriod']  
                        if 'start' in bounds_period:  
                            bounds_period['start'] = ensure_timezone_aware(bounds_period['start'])  
                        if 'end' in bounds_period:  
                            bounds_period['end'] = ensure_timezone_aware(bounds_period['end']) 
            # Remove 'code' field 
            if 'code' in resource_data:  
                del resource_data['code']

        if resource_type == "MedicationRequest": 
            # If 'dispenseRequest' and 'validityPeriod' are present in the resource data, ensure it is timezone aware
            if "dispenseRequest" in resource_data and "validityPeriod" in resource_data["dispenseRequest"]:  
                if "start" in resource_data["dispenseRequest"]["validityPeriod"]:  
                    resource_data["dispenseRequest"]["validityPeriod"]["start"] = ensure_timezone_aware(resource_data["dispenseRequest"]["validityPeriod"]["start"])
            # If 'medication' field is not present in the resource data, copy the 'medicationCodeableConcept' details
            if "medication" not in resource_data and 'medicationCodeableConcept' in resource_data:  
                resource_data["medication"] = {  
                    "concept": resource_data.pop("medicationCodeableConcept")
                }  
            
        if resource_type == "AllergyIntolerance":
            # Ensure fields are is timezone aware
            if "note" in resource_data:  
                for note in resource_data["note"]:  
                    if "time" in note:  
                        note["time"] = ensure_timezone_aware(note["time"])
            # Remove 'reaction' field
            if "reaction" in resource_data:  
                del resource_data["reaction"]
            # Remove 'type' field
            if "type" in resource_data:  
                del resource_data["type"]
        
        # Ensure fields are timezone aware
        if "effectiveDateTime" in resource_data:  
            resource_data["effectiveDateTime"] = ensure_timezone_aware(resource_data["effectiveDateTime"])  
        if "authoredOn" in resource_data:  
            resource_data["authoredOn"] = ensure_timezone_aware(resource_data["authoredOn"])  
        if "recordedDate" in resource_data:  
            resource_data["recordedDate"] = ensure_timezone_aware(resource_data["recordedDate"])  
        if "onsetDateTime" in resource_data:  
            resource_data["onsetDateTime"] = ensure_timezone_aware(resource_data["onsetDateTime"])  
        if "issued" in resource_data:  
            resource_data["issued"] = ensure_timezone_aware(resource_data["issued"])  
        if "validityPeriod" in resource_data and "start" in resource_data["validityPeriod"]:  
            resource_data["validityPeriod"]["start"] = ensure_timezone_aware(resource_data["validityPeriod"]["start"])

        # Map resource types to their respective classes
        resource_class_map = {  
            "Patient": Patient,  
            "Condition": Condition,  
            "Encounter": Encounter,  
            "Appointment": Appointment,  
            "Observation": Observation,  
            "ServiceRequest": ServiceRequest,  
            "MedicationRequest": MedicationRequest,  
            "AllergyIntolerance": AllergyIntolerance  
        }  

        # Check if the resource type is supported  
        if resource_type not in resource_class_map:  
            return {  
                "status": "error",  
                "message": f"Unsupported resource type: {resource_type}"  
            }, original_resource_data

        # Get the particular resource class
        resource_class = resource_class_map[resource_type]

        # Get required and optional fields for the particular resource from the HAPI FHIR server 
        required_fields, optional_fields = get_required_optional_fields(resource_class)  

        # Get all fields present in the generated resource data  
        present_fields = extract_all_fields(resource_data)
        
        try:  
            # Validate the resource using the FHIR resource model  
            resource_instance = resource_class(**resource_data)
    
            # Identify missing fields  
            missing_fields = set()      # Use a set to avoid duplicates  
            for field in required_fields:  
                if not field.endswith('__ext') and field not in optional_fields and field not in present_fields:
                    missing_fields.add(field)  
        
            missing_fields = list(missing_fields) 
            
            logging.info(f"Validation results for {resource_type}/{resource_data.get('id', 'unknown')}:")
            logging.info(f"Existing fields in the resource data for {resource_type}/{resource_data.get('id', 'unknown')}: {present_fields}")  
            #logging.info(f"Optional fields for {resource_type}/{resource_data.get('id', 'unknown')}: {optional_fields}")
            logging.info(f"Missing fields for {resource_type}/{resource_data.get('id', 'unknown')}: {missing_fields}")
            
            return {  
                "status": "success",  
                "resourceType": resource_type,
                "message": f"Resource {resource_type}/{resource_data.get('id', 'unknown')} is valid."  
            }, original_resource_data
        
        except ValidationError as e:
            # Identify missing fields  
            missing_fields = set()      # Use a set to avoid duplicates  
            for field in required_fields:  
                if not field.endswith('__ext') and field not in optional_fields and field not in present_fields:
                    missing_fields.add(field)  
        
            missing_fields = list(missing_fields) 

            logging.info(f"Validation results for {resource_type}/{resource_data.get('id', 'unknown')}:")
            logging.info(f"Existing fields in the resource data for {resource_type}/{resource_data.get('id', 'unknown')}: {present_fields}")  
            #logging.info(f"Optional fields for {resource_type}/{resource_data.get('id', 'unknown')}: {optional_fields}")
            logging.info(f"Missing fields for {resource_type}/{resource_data.get('id', 'unknown')}: {missing_fields}")
            
            return {  
                "status": "error", 
                "resourceType": resource_type, 
                "message": f"Resource {resource_type}/{resource_data.get('id', 'unknown')} validation failed. Error: {str(e)}"  
            }, original_resource_data
        
    except ValueError as e:
        return {  
            "status": "error",
            "resourceType": resource_type,
            "message": str(e)
        }, original_resource_data

# Function to validate the entire FHIR data bundle
def validate_fhir_data(file_path):
    logging.info('Validating FHIR bundle.')

    # Read the generated FHIR bundle from the file
    original_file_path = file_path
    with open(original_file_path, "r") as json_file:  
        file_content = json_file.read()  
        if not file_content.strip():  
            raise ValueError("JSON file is empty")
    
    fhir_resource = json.loads(file_content)
    logging.info(f"Read FHIR bundle from file: {original_file_path}")

    # Keep a copy of the original data for initial validation  
    original_fhir_resource = json.loads(json.dumps(fhir_resource))
    
    try:
        initial_validation_results = []  # Empty list to store results of initial validation
        validation_success = True        # Var to store the validation status

        # Convert the provided JSON structure into a FHIR bundle format if necessary  
        if 'entry' not in original_fhir_resource:  
            entries = []  
            for key, resource in original_fhir_resource.items():  
                if isinstance(resource, list):  
                    for res in resource:  
                        entries.append({"resource": res})  
                else:  
                    entries.append({"resource": resource})  
            original_fhir_resource = {  
                "resourceType": "Bundle",  
                "type": "collection",  
                "entry": entries  
            }  
            logging.info("Converted JSON to FHIR bundle format.")

        if original_fhir_resource.get("resourceType") == "Bundle":
            # Validate each resource in the bundle
            for entry in original_fhir_resource.get('entry', []):
                resource_data = entry.get("resource")

                # Check if resourceType is missing
                if not resource_data or 'resourceType' not in resource_data:
                    logging.error(f"Missing 'resourceType' in resource: {json.dumps(resource_data)}")
                    initial_validation_results.append({
                        "status": "error",  
                        "message": f"Missing 'resourceType' in resource {resource_data}"
                    })
                    validation_success = False
                    continue
                
                resource_type = resource_data.get("resourceType")
                initial_validation_result, _ = validate_individual_fhir_resource(resource_type, resource_data) 
                initial_validation_results.append(initial_validation_result)
                if initial_validation_result["status"] == "error":  
                    validation_success = False

            # Validate the Bundle itself
            logging.info("Validating the entire FHIR bundle.")
            try:
                Bundle(**original_fhir_resource)
            except ValidationError as e:
                initial_validation_results.insert(0, {
                    "status": "error",  
                    "message": f"Bundle validation failed: {str(e)}"
                })
                validation_success = False

        else:
            resource_type = original_fhir_resource.get("resourceType")
            initial_validation_result, _ = validate_individual_fhir_resource(resource_type, original_fhir_resource) 
            initial_validation_results.append(initial_validation_result)
            if initial_validation_result["status"] == "error":  
                validation_success = False
        
        # If original FHIR bundle doesn't contain any errors after validation
        if validation_success:
            initial_validation_response = {  
                "status": "success",  
                "message": "Validation of original bundle completed successfully.",  
                "initial_validation": {  
                    "status": "success",    
                    "filePath": original_file_path,  
                    "message": "Original FHIR Bundle and resourceTypes are valid. No re-validation needed.",  
                    "results": initial_validation_results  
                }
            }
            # Convert validated data to JSON string  
            initial_validation_response_json = json.dumps(initial_validation_response, indent=2)  

            return func.HttpResponse( 
                initial_validation_response_json, 
                status_code=200,
                mimetype="application/json"  
            )
            
        # Else if original FHIR bundle contains errors after validation, proceed with re-validation
        else:
            # Extract the id from the original file name  
            base_filename = os.path.basename(original_file_path)
            if base_filename.startswith("generated_fhir_bundle_"):
                # If original filename is "generated_fhir_bundle_{patiendID}"                            [normal case]
                base_id = base_filename.replace("generated_fhir_bundle_", "").replace(".json", "")
                # Store the modified data in a FHIR bundle dyanmically with base patientID
                new_file_path = f"fhir_data_validation/validated_fhir_bundle_{base_id}.json"
            else:      # Store the modified data in a FHIR bundle dyanmically with current datetime       [edge case]
                new_file_path = f"fhir_data_validation/validated_fhir_bundle_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    
            # Re-validate the entire bundle  
            validation_results = []         # Empty list to store results of final validation 
            
            # Keep a copy of the original data for final validation  
            validated_fhir_resource = json.loads(json.dumps(fhir_resource))

            # Convert the provided JSON structure into a FHIR bundle format if necessary  
            if 'entry' not in validated_fhir_resource:  
                entries = []  
                for key, resource in validated_fhir_resource.items():  
                    if isinstance(resource, list):  
                        for res in resource:  
                            entries.append({"resource": res})  
                    else:  
                        entries.append({"resource": resource})  
                validated_fhir_resource = {  
                    "resourceType": "Bundle",  
                    "type": "collection",  
                    "entry": entries  
                }  
                logging.info("Converted JSON to FHIR bundle format.")
            else:  
                if 'type' not in validated_fhir_resource:  
                    validated_fhir_resource['type'] = 'collection'  
                    logging.info("Set the bundle type to 'collection'.")  

            if validated_fhir_resource.get("resourceType") == "Bundle":  
                for entry in validated_fhir_resource.get('entry', []):  
                    validated_resource_data = entry.get("resource")  
                    
                    if not validated_resource_data or 'resourceType' not in validated_resource_data:  
                        validation_results.append({  
                            "status": "error",  
                            "message": f"Missing 'resourceType' in resource {validated_resource_data}"  
                        })  
                        continue  
                    
                    resource_type = validated_resource_data.get("resourceType")  
                    final_validation_result, _ = validate_individual_fhir_resource(resource_type, validated_resource_data)
                    validation_results.append(final_validation_result)  
                
                # Validate the Bundle itself
                logging.info("Validating the entire FHIR bundle.")
                try:  
                    Bundle(**validated_fhir_resource)
                except ValidationError as e:  
                    validation_results.insert(0, {  
                        "status": "error",  
                        "message": f"Re-validation of bundle failed: {str(e)}"  
                    })  
            else:  
                resource_type = validated_fhir_resource.get("resourceType")  
                final_validation_result, _ = validate_individual_fhir_resource(resource_type, validated_fhir_resource)
                validation_results.append(final_validation_result)
            
            # Convert validated data to JSON string  
            validated_data_json = json.dumps(validated_fhir_resource, indent=2)  
            logging.info("FHIR bundle validation process completed successfully.")

            # Store the JSON file in Azure Blob Storage  
            container_name = os.environ["BLOB_CONTAINER_NAME"]
            file_name = new_file_path
            
            # Initialize the BlobServiceClient with connection string  
            blob_service_client = BlobServiceClient.from_connection_string("BLOB_CONNECTION_STRING")  
            container_client = blob_service_client.get_container_client(container_name)  
            blob_client = container_client.get_blob_client(file_name)  

            # Upload the JSON string to the blob  
            blob_client.upload_blob(validated_data_json, overwrite=True)
            blob_url = blob_client.url         # Fetch the URL of the uploaded blob  

            # Return response for the newly generated validated bundle using ValidationAPI
            initial_validation_response = {  
                "status": "error",
                "filePath": original_file_path, 
                "message": "Initial FHIR Bundle contains errors. Generating validated bundle."
            }
            re_validation_response = {  
                "status": "success",
                "filePath": f"Validated FHIR bundle '{new_file_path}' available to download from Postman",
                "message": "FHIR Bundle and resourceTypes are valid after re-validation.",  
                "blobUrl": blob_url,
                "results": validation_results  
            }
            
            # Create response dictionary
            postman_response = {  
                "status": "success",  
                "message": "Validation of original bundle and validated bundle completed successfully.",  
                "initial_validation": initial_validation_response, 
                "re_validation": re_validation_response
            } 
            # Convert response dictionary to JSON string  
            postman_response_json = json.dumps(postman_response, indent=2)  

            # Return the JSON content in the response with headers to prompt download  
            logging.info("Validated FHIR bundle available to download from Postman. Click on the 'Save Response' button and choose 'Save to a file' to download the JSON file.") 
            return func.HttpResponse(  
                postman_response_json,
                status_code=200,  
                headers={  
                    "Content-Disposition": f"attachment; filename={new_file_path}",  
                    "Content-Type": "application/json"  
                }  
            )
    
    except Exception as e:  
        logging.error(f"An unexpected error occurred: {str(e)}") 
        return func.HttpResponse(  
            f"An unexpected error occurred: {str(e)}", 
              status_code=500
        )
