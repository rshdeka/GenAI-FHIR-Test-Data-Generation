import logging  
import os
import json
import azure.functions as func
import requests.exceptions
from OpenAI import callGptEndpoint
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


fhir_resource_generation_blueprint=func.Blueprint()


# Function to generate FHIR data using GPT
def generate_fhir_data_using_gpt(prompt):
    user_message = {  
        "role": "user",  
        "content": prompt  
    }  
  
    messages = [user_message]  
    gpt_options = {
        "engine": os.environ["AZURE_OPENAI_MODEL"],  
        "messages": messages,  
        "temperature": 0.7,  
        "max_tokens": 4096,
        "timeout": 300
    }
    
    try:
        gpt_response = callGptEndpoint(gpt_options)
        if not gpt_response or not gpt_response.choices:  
            logging.error("Error occurred while calling GPT endpoint or no choices in response.")  
            return None  
    
        # Extract the generated content
        response = gpt_response.choices[0].message.content.strip() if gpt_response.choices[0].message.content else None  
        if response:  
            logging.info("GPT response processed successfully.")  
        else:  
            logging.error("No content found in GPT response.")
        return response
    except requests.exceptions.RequestException as e:  
        if e.response and e.response.status_code == 504:  
            logging.error("504 Gateway Timeout error occurred.")  
        else:  
            logging.error(f"An error occurred while calling GPT endpoint: {e}")  
        return None
    except Exception as e:  
        logging.error(f"An error occurred while calling GPT endpoint: {e}")  
        return None


# Function to generate patient data based on user input
def generate_patient_data(data_elements=None, input_data=None):
    logging.info('Generating patient data for the FHIR resource.')

    prompt = '''
    Generate realistic healthcare data in the FHIR format containing the Patient resourceType including details such as -
      - resourceType, id, meta (versionId and lastUpdated), identifiers, names, telecoms, gender, birth date, 
        addresses, marital status, link, contacts, communication, general practitioner, managing organization
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''
    if data_elements:  
        prompt += f" with data elements: {data_elements}"  
    if input_data:  
        prompt += f" with input data: {input_data}"  
  
    return generate_fhir_data_using_gpt(prompt)


# Function to handle the inclusion of condition data based on user input
def generate_condition_data(patient_id, data_elements=None, input_data=None):  
    prompt = f'''
    Generate realistic healthcare data in the FHIR format containing the Condition resourceType linked to Patient FHIR ID {patient_id} including details such as -
      - resourceType, id, meta (versionId and lastUpdated), identifiers, clinical status, verification status, 
        categories, codes, severity, subject, onset period (start and end dates), recorded date, encounter
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''
    if data_elements:  
        prompt += f" with data elements: {data_elements}"  
    if input_data:  
        prompt += f" with input data: {input_data}" 

    return generate_fhir_data_using_gpt(prompt)


# Function to handle the inclusion of encounter data based on user input
def generate_encounter_data(patient_id, data_elements=None, input_data=None):        
    prompt = f'''      
    Generate realistic healthcare data in the FHIR format containing the Encounter resourceType linked to Patient FHIR ID {patient_id} including details such as -          
      - resourceType, id, meta (versionId and lastUpdated), identifiers, status, type, subject, location, diagnosis
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''      
    if data_elements:            
        prompt += f" with data elements: {data_elements}"        
    if input_data:            
        prompt += f" with input data: {input_data}"

    return generate_fhir_data_using_gpt(prompt)


# Function to handle the inclusion of appointment data based on user input  
def generate_appointment_data(patient_id, data_elements=None, input_data=None):  
    prompt = f'''
    Generate realistic healthcare data in the FHIR format containing the Appointment resourceType linked to Patient FHIR ID {patient_id} including details such as -  
      - resourceType, id, meta (versionId and lastUpdated), identifiers, status, service category, appointment type,
        start and end times, minutes duration, creation date, patient instruction
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''  
    if data_elements:  
        prompt += f" with data elements: {data_elements}"  
    if input_data:  
        prompt += f" with input data: {input_data}"  
    
    return generate_fhir_data_using_gpt(prompt)


# Function to handle the inclusion of observation data based on user input
def generate_observation_data(patient_id, category, data_elements=None, input_data=None):
    valid_categories = {'vital-signs', 'laboratory'}  
      
    # Check for invalid categories
    invalid_categories = [cat for cat in category if cat not in valid_categories]  
    if invalid_categories:  
        logging.error(f"Invalid category provided: {invalid_categories}")  
        return None  

    prompts = []      # Initialize empty list to store different prompts
    
    if 'vital-signs' in category:
        heart_rate_prompt = f'''
        Generate realistic healthcare data in the FHIR format containing an Observation resourceTypes linked to Patient FHIR ID {patient_id} for heart rate.
        The Observation resource should include details such as -
           - resourceType, id, meta (versionId and lastUpdated), identifiers, based on, status, category, code, subject, 
             encounter, effective date/time, issued date, performer, and value quantity
        Make sure none of the specified fields are missing.
        Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
        '''
        if data_elements:  
            heart_rate_prompt += f" with data elements: {data_elements}"  
        if input_data:
            if isinstance(input_data, dict) and 'vital-signs' in input_data:
                heart_rate_prompt += f" with input data: {input_data.get('vital-signs')}"  
            else:    
                heart_rate_prompt += f" with input data: {input_data}"  
        prompts.append(heart_rate_prompt)

        blood_pressure_prompt = f'''
        Generate realistic healthcare data in the FHIR format containing an Observation resourceTypes linked to Patient FHIR ID {patient_id} blood-pressure, including components for systolic and diastolic blood pressure.
        The Observation resource should include details such as -
          - resourceType, id, meta (versionId and lastUpdated), identifiers, based on, status, category, code, subject, 
            encounter, effective date/time, issued date, performer, and components
        Make sure none of the specified fields are missing.
        Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
        '''
        if data_elements:  
            blood_pressure_prompt += f" with data elements: {data_elements}"  
        if input_data:
            if isinstance(input_data, dict) and 'vital-signs' in input_data:
                blood_pressure_prompt += f" with input data: {input_data.get('vital-signs')}"  
            else:    
                blood_pressure_prompt += f" with input data: {input_data}"  
        prompts.append(blood_pressure_prompt)
    
    if 'laboratory' in category:  
        laboratory_prompt = f'''
        Generate realistic healthcare data in the FHIR format containing the Observation resourceType linked to Patient FHIR ID {patient_id} including details such as - 
          - resourceType, id, meta (versionId and lastUpdated), identifiers, based on, status, category, code, subject, 
            encounter, effective date/time, issued date, value string, value quantity, specimen, and reference range
        Make sure none of the specified fields are missing.
        Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
        '''
        if data_elements:  
            laboratory_prompt += f" with data elements: {data_elements}"  
        if input_data:  
            if isinstance(input_data, dict) and 'laboratory' in input_data:
                laboratory_prompt += f" with input data: {input_data.get('laboratory')}"  
            else:    
                laboratory_prompt += f" with input data: {input_data}"  
        prompts.append(laboratory_prompt)
    
    observation_data = []    # Initialize empty list to store different prompt responses
    
    # Iterate through each prompt generated for the valid categories
    for prompt in prompts:
        # Generate FHIR data using GPT based on the prompt
        response = generate_fhir_data_using_gpt(prompt)  
        if response:
            observation_data.append(response)     # If the response is valid, append it to the obs_data list
        else:  
            logging.error(f"Failed to generate Observation data for prompt category: {category}")
            return None
    
    # Return the list of responses containing the generated observation data
    return observation_data


# Function to handle the inclusion of service request data based on user input  
def generate_service_request_data(patient_id, data_elements=None, input_data=None):  
    prompt = f'''  
    Generate realistic healthcare data in the FHIR format containing the ServiceRequest resourceType linked to Patient FHIR ID {patient_id} including details such as -  
      - resourceType, id, meta (versionId and lastUpdated), identifiers, based on, status, intent, category, subject, 
        encounter, occurrence timing, authored on date, requester, specimen
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''  
    if data_elements:  
        prompt += f" with data elements: {data_elements}"  
    if input_data:  
        prompt += f" with input data: {input_data}"  
  
    return generate_fhir_data_using_gpt(prompt)


# Function to handle the inclusion of medication request data based on user input  
def generate_medication_request_data(patient_id, data_elements=None, input_data=None):  
    prompt = f'''  
    Generate realistic healthcare data in the FHIR format containing the MedicationRequest resourceType linked to Patient FHIR ID {patient_id} including details such as -  
      - resourceType, id, meta (versionId and lastUpdated), identifiers, status, intent, category, medication, medication codeable concept, 
        subject, encounter, authored on date, requester, recorder, course of therapy type, dosage instruction, dispense request, prior prescription
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''  
    if data_elements:  
        prompt += f" with data elements: {data_elements}"  
    if input_data:  
        prompt += f" with input data: {input_data}"  
    
    return generate_fhir_data_using_gpt(prompt)


# Function to handle the inclusion of allergy intolerance data based on user input  
def generate_allergy_intolerance_data(patient_id, data_elements=None, input_data=None):  
    prompt = f'''  
    Generate realistic healthcare data in the FHIR format containing the AllergyIntolerance resourceType linked to Patient FHIR ID {patient_id} including details such as -  
      - resourceType, id, meta (versionId and lastUpdated), identifiers, clinical status, verification status, codes, patient, recorded date
    Make sure none of the specified fields are missing.
    Also, add appropriate SNOMED, LOINC, and RXNorm codes wherever necessary.
    '''  
    if data_elements:  
        prompt += f" with data elements: {data_elements}"  
    if input_data:  
        prompt += f" with input data: {input_data}"  
    
    return generate_fhir_data_using_gpt(prompt)


# Utility function to clean up and extract valid JSON from generated FHIR data
def clean_fhir_data(fhir_data):  
    try:
        # Handle JSON objects by finding the first and last braces
        start_index = fhir_data.find("{")  
        end_index = fhir_data.rfind("}") + 1 
        cleaned_data = fhir_data[start_index:end_index]     # Extract the JSON string
        return json.loads(cleaned_data)  
    except json.JSONDecodeError as e:
        logging.error(f"Error occurred while cleaning FHIR data: {e}")
        logging.error("Generated FHIR data could not be processed due to an error.")
        return None


def generate_fhir_bundle(user_parameters):
    logging.info('Generating FHIR resource.')

    # -------------------- Combined FHIR data -------------------------
    # Combine FHIR bundle (patient, condition, encounter, appointment, observation, service request, medication request, allergy intolerance data)
    combined_data = {            # Initialize
        "resourceType": "Bundle",
        "type": "collection", 
        "entry": []  
    }
    
    # Combined success data for the FHIR bundle to return as a Postman response
    success_data = {}            # Initialize a dictionary to store success data
    combined_success_data = {}

    # -------------------- Patient data -------------------------
    # Initialize patient data
    patient_data_elements = None  
    patient_input_data = None
    
    # Check if the resource needs updates
    if user_parameters.get("update_patient", False):
        logging.info('Resource needs updates. Collecting patient user input for data elements and input data.')

        # Collect user input for data elements and input data  
        patient_data_elements = user_parameters.get("patient_data_elements")  
        patient_input_data = user_parameters.get("patient_input_data")  

        if not patient_data_elements or not patient_input_data:  
            logging.error("Data elements or input data not provided for patient updates.")  
            return func.HttpResponse(  
                "Data elements or input data not provided for patient updates.",  
                status_code=400  
            )
        
        patient_data = generate_patient_data(patient_data_elements, patient_input_data)  
    # Else if the resource doesn't need updates
    else:         
        patient_data = generate_patient_data()    # Simply generate patient data

    if not patient_data:  
        return func.HttpResponse("Failed to generate Patient data.", status_code=500)  
      
    try:
        # Clean up the generated FHIR data to extract valid JSON
        patient_data_json = clean_fhir_data(patient_data)  
        if not patient_data_json:  
            return func.HttpResponse("Failed to decode generated Patient data.", status_code=500)
        
        # Append patient data to the combined JSON FHIR bundle
        if patient_data_json:  
            combined_data["entry"].append({  
                "fullUrl": f"urn:uuid:{patient_data_json['id']}",
                "resource": patient_data_json  
            })
            logging.info(f"Patient Data for {patient_data_json['id']} appended successfully.")
        
        # Set success data for patient
        patient_id = patient_data_json.get("id", "unknown_patient")
        success_data["patient"] = {  
            "message": f"Patient data for ID: Patient/{patient_id} generated successfully.",
            "patient_data_elements": patient_data_elements
        }

        # Append patient success data to the combined success data
        combined_success_data["patient"] = success_data["patient"] 

        # -------------------- Condition data -------------------------
        # Initialize condition data
        condition_data_elements = None  
        condition_input_data = None  

        # Generate condition data if specified by user
        condition_data_json = None  
        if user_parameters.get("include_condition", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates
            if user_parameters.get("update_condition", False):  
                logging.info('Resource needs updates. Collecting condition user input for data elements and input data.')  
  
                # Collect user input for data elements and input data  
                condition_data_elements = user_parameters.get("condition_data_elements")  
                condition_input_data = user_parameters.get("condition_input_data")  
  
                if not condition_data_elements or not condition_input_data:  
                    logging.error("Data elements or input data not provided for condition updates.")  
                    return func.HttpResponse(  
                        "Data elements or input data not provided for condition updates.",  
                        status_code=400  
                    )
                
                condition_data = generate_condition_data(patient_id, condition_data_elements, condition_input_data)  
            # Else if the resource doesn't need updates
            else:         
                condition_data = generate_condition_data(patient_id)    # Simply generate condition data for the patient
  
            if not condition_data:  
                return func.HttpResponse("Failed to generate Condition data.", status_code=500)

            try:
                # Clean up the generated FHIR data to extract valid JSON
                condition_data_json = clean_fhir_data(condition_data)  
                if not condition_data_json:  
                    return func.HttpResponse("Failed to decode generated Condition data.", status_code=500)
                logging.info("Condition data generated successfully.")

                # Append condition data to the combined JSON FHIR bundle
                if condition_data_json:  
                    combined_data["entry"].append({  
                        "fullUrl": f"urn:uuid:{condition_data_json['id']}",  
                        "resource": condition_data_json  
                    })  
                    logging.info(f"Condition Data for {condition_data_json['id']} appended successfully.")

                # Set success data for condition  
                if condition_data_json:  
                    condition_id = condition_data_json.get("id", "unknown_condition")  
                    success_data["condition"] = {  
                        "message": f"Condition data for Condition/{condition_id} generated successfully.",  
                        "condition_data_elements": condition_data_elements
                    } 

                # Append condition success data to the combined success data
                if condition_data_json:
                    combined_success_data["condition"] = success_data["condition"] 

            except Exception as e:  
                logging.error(f"Exception while processing Condition data: {e}")  
                logging.error(f"Generated Condition data: {condition_data}")  
                return func.HttpResponse(
                    "An error occurred while processing the generated Condition data.", 
                    status_code=500
                )
        
        # -------------------- Encounter data -------------------------
        # Initialize encounter data
        encounter_data_elements = None  
        encounter_input_data = None 

        # Generate encounter data if specified by user  
        encounter_data_json = None  
        if user_parameters.get("include_encounter", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates  
            if user_parameters.get("update_encounter", False):  
                logging.info('Resource needs updates. Collecting encounter user input for data elements and input data.')  
                
                # Collect user input for data elements and input data  
                encounter_data_elements= user_parameters.get("encounter_data_elements")  
                encounter_input_data = user_parameters.get("encounter_input_data")  
  
                if not encounter_data_elements or not encounter_input_data:  
                    logging.error("Data elements or input data not provided for encounter updates.")  
                    return func.HttpResponse(  
                        "Data elements or input data not provided for encounter updates.",  
                        status_code=400  
                    )
                
                encounter_data = generate_encounter_data(patient_id, encounter_data_elements, encounter_input_data)
            # Else if the resource doesn't need updates
            else:
                encounter_data = generate_encounter_data(patient_id)    # Simply generate encounter data for the patient  
  
            if not encounter_data:  
                return func.HttpResponse("Failed to generate Encounter data.", status_code=500)
            
            try:
                # Clean up the generated FHIR data to extract valid JSON
                encounter_data_json = clean_fhir_data(encounter_data)  
                if not encounter_data_json:  
                    return func.HttpResponse("Failed to decode generated Encounter data.", status_code=500)
                logging.info("Encounter data generated successfully.")

                # Append encounter data to the combined JSON FHIR bundle
                if encounter_data_json:  
                    combined_data["entry"].append({  
                        "fullUrl": f"urn:uuid:{encounter_data_json['id']}",
                        "resource": encounter_data_json  
                    })
                    logging.info(f"Encounter Data for {encounter_data_json['id']} appended successfully.")

                # Set success data for encounter
                if encounter_data_json:  
                    encounter_id = encounter_data_json.get("id", "unknown_encounter")  
                    success_data["encounter"] = {  
                        "message": f"Encounter data for Encounter/{encounter_id} generated successfully.",  
                        "encounter_data_elements": encounter_data_elements  
                    } 

                # Append encounter success data to the combined success data
                if encounter_data_json:
                    combined_success_data["encounter"] = success_data["encounter"] 

            except Exception as e:  
                logging.error(f"Exception while processing Encounter data: {e}")  
                logging.error(f"Generated Encounter data: {encounter_data}")  
                return func.HttpResponse(  
                    "An error occurred while processing the generated Encounter data.",  
                    status_code=500  
                )
        
        # -------------------- Appointment data -------------------------
        # Initialize appointment data
        appointment_data_elements = None  
        appointment_input_data = None 

        # Generate appointment data if specified by user  
        appointment_data_json = None  
        if user_parameters.get("include_appointment", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates  
            if user_parameters.get("update_appointment", False):  
                logging.info('Resource needs updates. Collecting appointment user input for data elements and input data.')  
                
                # Collect user input for data elements and input data  
                appointment_data_elements = user_parameters.get("appointment_data_elements")  
                appointment_input_data = user_parameters.get("appointment_input_data")  
  
                if not appointment_data_elements or not appointment_input_data:  
                    logging.error("Data elements or input data not provided for appointment updates.")  
                    return func.HttpResponse(  
                        "Data elements or input data not provided for appointment updates.",  
                        status_code=400  
                    )
                
                appointment_data = generate_appointment_data(patient_id, appointment_data_elements, appointment_input_data)  
            # Else if the resource doesn't need updates
            else:  
                appointment_data = generate_appointment_data(patient_id)  # Simply generate appointment data for the patient  
  
            if not appointment_data:  
                return func.HttpResponse("Failed to generate Appointment data.", status_code=500)
            
            try:
                # Clean up the generated FHIR data to extract valid JSON
                appointment_data_json = clean_fhir_data(appointment_data)  
                if not appointment_data_json:  
                    return func.HttpResponse("Failed to decode generated Appointment data.", status_code=500)
            
                logging.info("Appointment data generated successfully.")

                # Append appointment data to the combined JSON FHIR bundle
                if appointment_data_json:  
                    combined_data["entry"].append({  
                        "fullUrl": f"urn:uuid:{appointment_data_json['id']}",  
                        "resource": appointment_data_json  
                    })          
                    logging.info("Appointment data appended successfully.")

                # Set success data for appointment  
                if appointment_data_json:  
                    appointment_id = appointment_data_json.get("id", "unknown_appointment")  
                    success_data["appointment"] = {  
                        "message": f"Appointment data for Appointment/{appointment_id} generated successfully.",  
                        "appointment_data_elements": appointment_data_elements
                    }

                # Append appointment success data to the combined success data
                if appointment_data_json:
                    combined_success_data["appointment"] = success_data["appointment"] 

            except Exception as e:  
                logging.error(f"Exception while processing Appointment data: {e}")  
                logging.error(f"Generated Appointment data could not be processed due to an error.")  
                return func.HttpResponse(  
                    "An error occurred while processing the generated Appointment data.",  
                    status_code=500  
                )
        
        # -------------------- Observation data -------------------------
        # Initialize observation data
        observation_data_elements = None  
        observation_input_data = None
        observation_category = None

        # Generate observation data if specified by user  
        observation_data_json = None  
        if user_parameters.get("include_observation", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates  
            if user_parameters.get("update_observation", False):  
                logging.info('Resource needs updates. Collecting observation user input for data elements and input data.')  
                
                # Collect user input for data elements and input data  
                observation_data_elements = user_parameters.get("observation_data_elements")  
                observation_input_data = user_parameters.get("observation_input_data")  
                observation_category = user_parameters.get("observation_category")
  
                if not observation_data_elements or not observation_input_data or not observation_category:  
                    logging.error("Data elements, input data, or category not provided for observation updates.")  
                    return func.HttpResponse(  
                        "Data elements, input data, or category not provided for observation updates.",  
                        status_code=400  
                    )

                observation_data = generate_observation_data(patient_id, observation_category, observation_data_elements, observation_input_data)
            # Else if the resource doesn't need updates
            else:  
                observation_category = user_parameters.get("observation_category")
                if not observation_category:  
                    logging.error("Category not provided for observation data generation.")  
                    return func.HttpResponse(  
                        "Category not provided for observation data generation.",  
                        status_code=400  
                    )
  
                observation_data = generate_observation_data(patient_id, observation_category)
        
            if not observation_data:  
                return func.HttpResponse("Failed to generate Observation data.", status_code=500)

            try:
                for obs in observation_data:
                    try:
                        # Clean up the generated FHIR data to extract valid JSON
                        observation_data_json = clean_fhir_data(obs) 
                        if not observation_data_json:  
                            return func.HttpResponse("Failed to decode generated observation data.", status_code=500)

                        # Append observation data to the combined JSON FHIR bundle one-at-a-time
                        observation_id = observation_data_json.get("id", "unknown_observation")
                        combined_data["entry"].append({  
                            "fullUrl": f"urn:uuid:{observation_id}",  
                            "resource": observation_data_json
                        })
                        logging.info(f"Observation Data for {observation_id} appended successfully.")
                        observation_entry = {  
                            "message": f"Observation data for ID:Observation/{observation_id} generated successfully."  
                        }  
                        if observation_category:  
                            observation_entry["observation_category"] = observation_category
                        if observation_data_elements:  
                            observation_entry["observation_data_elements"] = observation_data_elements  
                        
                        # Set success data for all the observation entries in a list
                        if "observation" not in success_data:  
                            success_data["observation"] = []  
                        success_data["observation"].append(observation_entry)  
  
                        # Append observation success data to the combined success data  
                        combined_success_data["observation"] = success_data["observation"]  
                    
                    except Exception as e:  
                        logging.error(f"Exception while processing Observation data for ID:Observation/{observation_id}: {e}")
                        return func.HttpResponse(  
                            f"An error occurred while processing the generated Observation data for ID:Observation/{observation_id}",  
                            status_code=500  
                        )
            
            except Exception as e:  
                logging.error(f"Exception while processing Observation data: {e}")
                return func.HttpResponse(  
                    "An error occurred while processing the generated Observation data.",  
                    status_code=500  
                )
        
        # -------------------- Service Request data -------------------------
        # Initialize Service Request data
        service_request_data_elements = None  
        service_request_input_data = None 

        # Generate service request data if specified by user  
        service_request_data_json = None  
        if user_parameters.get("include_service_request", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates  
            if user_parameters.get("update_service_request", False):  
                logging.info('Resource needs updates. Collecting service request user input for data elements and input data.')  
                
                # Collect user input for data elements and input data  
                service_request_data_elements = user_parameters.get("service_request_data_elements")  
                service_request_input_data = user_parameters.get("service_request_input_data")  
  
                if not service_request_data_elements or not service_request_input_data:  
                    logging.error("Data elements or input data not provided for service request updates.")  
                    return func.HttpResponse(  
                        "Data elements or input data not provided for service request updates.",  
                        status_code=400  
                    )  
  
                service_request_data = generate_service_request_data(patient_id, service_request_data_elements, service_request_input_data)
            # Else if the resource doesn't need updates
            else:  
                service_request_data = generate_service_request_data(patient_id)  # Simply generate service request data for the patient  
  
            if not service_request_data:  
                return func.HttpResponse("Failed to generate Service Request data.", status_code=500)
            
            try:
                # Clean up the generated FHIR data to extract valid JSON
                service_request_data_json = clean_fhir_data(service_request_data)  
                if not service_request_data_json:  
                    return func.HttpResponse("Failed to decode generated Service Request data.", status_code=500)  
                
                logging.info("Service Request data generated successfully.")

                # Append service-request data to the combined JSON FHIR bundle
                if service_request_data_json:  
                    combined_data["entry"].append({  
                        "fullUrl": f"urn:uuid:{service_request_data_json['id']}",  
                        "resource": service_request_data_json  
                    })
                    logging.info(f"Service Request Data for {service_request_data_json['id']} appended successfully.")

                # Set success data for service-request  
                if service_request_data_json:  
                    service_request_id = service_request_data_json.get("id", "unknown_service_request")  
                    success_data["service_request"] = {  
                        "message": f"ServiceRequest data for ServiceRequest/{service_request_id} generated successfully.",
                        "service_request_data_elements": service_request_data_elements
                    }

                # Append service_request success data to the combined success data
                if service_request_data_json:
                    combined_success_data["service_request"] = success_data["service_request"] 

            except Exception as e:  
                logging.error(f"Exception while processing Service Request data: {e}")  
                logging.error(f"Generated Service Request data could not be processed due to an error.")  
                return func.HttpResponse(  
                    "An error occurred while processing the generated Service Request data.",  
                    status_code=500  
                )
        
        # -------------------- Medication Request data -------------------------
        # Initialize Medication Request data
        medication_request_data_elements = None  
        medication_request_input_data = None 

        # Generate medication request data if specified by user  
        medication_request_data_json = None  
        if user_parameters.get("include_medication_request", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates  
            if user_parameters.get("update_medication_request", False):  
                logging.info('Resource needs updates. Collecting medication request user input for data elements and input data.')  
                
                # Collect user input for data elements and input data  
                medication_request_data_elements = user_parameters.get("medication_request_data_elements")  
                medication_request_input_data = user_parameters.get("medication_request_input_data")
                
                if not medication_request_data_elements or not medication_request_input_data:
                    logging.error("Data elements or input data not provided for medication request updates.")  
                    return func.HttpResponse(  
                        "Data elements or input data not provided for medication request updates.",  
                        status_code=400  
                    )
                
                medication_request_data = generate_medication_request_data(patient_id, medication_request_data_elements, medication_request_input_data)
            # Else if the resource doesn't need updates
            else:  
                medication_request_data = generate_medication_request_data(patient_id)  # Simply generate medication request data for the patient  
        
            if not medication_request_data:  
                return func.HttpResponse("Failed to generate Medication Request data.", status_code=500)  
        
            try:
                # Clean up the generated FHIR data to extract valid JSON  
                medication_request_data_json = clean_fhir_data(medication_request_data)  
                if not medication_request_data_json:  
                    return func.HttpResponse("Failed to decode generated Medication Request data.", status_code=500)
                
                logging.info("Medication Request data generated successfully.")

                # Append medication-request data to the combined JSON FHIR bundle
                if medication_request_data_json:  
                    combined_data["entry"].append({  
                        "fullUrl": f"urn:uuid:{medication_request_data_json['id']}",  
                        "resource": medication_request_data_json  
                    })
                    logging.info(f"Medication Request Data for {medication_request_data_json['id']} appended successfully.")

                # Set success data for medication-request
                if medication_request_data_json:  
                    medication_request_id = medication_request_data_json.get("id", "unknown_medication_request")  
                    success_data["medication_request"] = {  
                        "message": f"MedicationRequest data for MedicationRequest/{medication_request_id} generated successfully.",  
                        "medication_request_data_elements": medication_request_data_elements
                    }

                # Append medication_request success data to the combined success data
                if medication_request_data_json:
                    combined_success_data["medication_request"] = success_data["medication_request"] 

            except Exception as e:  
                logging.error(f"Exception while processing Medication Request data: {e}")  
                logging.error(f"Generated Medication Request data could not be processed due to an error.")  
                return func.HttpResponse(  
                    "An error occurred while processing the generated Medication Request data.",  
                    status_code=500  
                )
        
        # -------------------- Allergy Intolerance data -------------------------
        # Initialize Allergy Intolerance data
        allergy_intolerance_data_elements = None  
        allergy_intolerance_input_data = None
        
        # Generate allergy intolerance data if specified by user  
        allergy_intolerance_data_json = None  
        if user_parameters.get("include_allergy_intolerance", False):  
            patient_id = patient_data_json.get("id")  
            if not patient_id:  
                logging.error("Patient ID not found in generated patient data.")  
                return func.HttpResponse("Patient ID not found.", status_code=500)
            
            # Check if the resource needs updates  
            if user_parameters.get("update_allergy_intolerance", False):  
                logging.info('Resource needs updates. Collecting allergy intolerance user input for data elements and input data.')  
                
                # Collect user input for data elements and input data  
                allergy_intolerance_data_elements = user_parameters.get("allergy_intolerance_data_elements")  
                allergy_intolerance_input_data = user_parameters.get("allergy_intolerance_input_data")  
    
                if not allergy_intolerance_data_elements or not allergy_intolerance_input_data:
                    logging.error("Data elements or input data not provided for allergy intolerance updates.")  
                    return func.HttpResponse(  
                        "Data elements or input data not provided for allergy intolerance updates.",  
                        status_code=400  
                    )  
                
                allergy_intolerance_data = generate_allergy_intolerance_data(patient_id, allergy_intolerance_data_elements, allergy_intolerance_input_data)
            # Else if the resource doesn't need updates
            else:  
                allergy_intolerance_data = generate_allergy_intolerance_data(patient_id)  # Simply generate allergy intolerance data for the patient  
        
            if not allergy_intolerance_data:  
                return func.HttpResponse("Failed to generate Allergy Intolerance data.", status_code=500)  
        
            try:
                # Clean up the generated FHIR data to extract valid JSON  
                allergy_intolerance_data_json = clean_fhir_data(allergy_intolerance_data)  
                if not allergy_intolerance_data_json:  
                    return func.HttpResponse("Failed to decode generated Allergy Intolerance data.", status_code=500)  
                
                logging.info("Allergy Intolerance data generated successfully.")

                # Append allergy-intolerance data to the combined JSON FHIR bundle
                if allergy_intolerance_data_json:  
                    combined_data["entry"].append({  
                        "fullUrl": f"urn:uuid:{allergy_intolerance_data_json['id']}",  
                        "resource": allergy_intolerance_data_json  
                    })
                    logging.info(f"Allergy Intolerance Data for {allergy_intolerance_data_json['id']} appended successfully.")

                # Set success data for allergy-intolerance  
                if allergy_intolerance_data_json:  
                    allergy_intolerance_id = allergy_intolerance_data_json.get("id", "unknown_allergy_intolerance")  
                    success_data["allergy_intolerance"] = {  
                        "message": f"AllergyIntolerance data for AllergyIntolerance/{allergy_intolerance_id} generated successfully.", 
                        "allergy_intolerance_data_elements": allergy_intolerance_data_elements
                    }

                # Append allergy_intolerance success data to the combined success data
                if allergy_intolerance_data_json:
                    combined_success_data["allergy_intolerance"] = success_data["allergy_intolerance"] 

            except Exception as e:  
                logging.error(f"Exception while processing Allergy Intolerance data: {e}")  
                logging.error(f"Generated Allergy Intolerance data could not be processed due to an error.")  
                return func.HttpResponse(  
                    "An error occurred while processing the generated Allergy Intolerance data.",  
                    status_code=500  
                )  
  
        # -------------------- Combined FHIR data -------------------------
        # Store the combined JSON in a separate file dyanmically with patient ID
        if patient_data_json and "id" in patient_data_json:  
            patient_id = patient_data_json["id"]  
        else:  
            patient_id = "unknown_patient"

        # Convert combined data into a JSON string  
        combined_data_json = json.dumps(combined_data, indent=2)  
        logging.info("FHIR bundle generation process completed successfully.") 

        # Store the JSON file in Azure Blob Storage  
        container_name = os.environ["BLOB_CONTAINER_NAME"]
        file_name = f"generated_fhir_bundle_{patient_id}.json"  
        
        # Initialize the BlobServiceClient with connection string  
        blob_service_client = BlobServiceClient.from_connection_string("BLOB_CONNECTION_STRING")  
        container_client = blob_service_client.get_container_client(container_name)  
        blob_client = container_client.get_blob_client(file_name)  

        # Upload the JSON string to the blob  
        blob_client.upload_blob(combined_data_json, overwrite=True)
        blob_url = blob_client.url         # Fetch the URL of the uploaded blob  

        # Create the response dictionary  
        response_content = {  
            "message": "FHIR data generated and stored successfully.", 
            "filePath": f"Generated FHIR bundle {file_name} available to download from Postman. ", 
            "blobUrl": blob_url,
            "success_data": combined_success_data
        }  
        # Convert response dictionary to JSON string  
        response_json = json.dumps(response_content, indent=2)  

        # Return the JSON content in the response with headers to prompt download  
        logging.info("Generated FHIR bundle available to download from Postman. Click on the 'Save Response' button and choose 'Save to a file' to download the JSON file.") 
        return func.HttpResponse(  
            response_json,
            status_code=200,  
            headers={  
                "Content-Disposition": f"attachment; filename=generated_fhir_bundle_{patient_id}.json",  
                "Content-Type": "application/json"  
            }  
        )  
    
    except Exception as e:  
        logging.error(f"Exception while processing Patient data: {e}")  
        logging.error(f"Generated Patient data could not be processed due to an error.")  
        return func.HttpResponse(  
                "An error occurred while processing the generated Patient data.",
                 status_code=500
        )
