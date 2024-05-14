from pathlib import Path
import numpy as np
import pandas as pd

from algorithm import Module, ModuleAssigner, Student

def validate_module_data(data:pd.DataFrame):
    errors = []
    required_columns = ["module_id", "module_name", "module_group", "semester", "credits", "capacity", "available_spaces", "required_modules", "mutually_excluded_modules"]
    for c in required_columns:
        if not c in data.columns:
            errors += [f"Column '{c}' was not found in the module data file"]
    return errors 

def load_module_data(filepath:Path):
    """Load the module data from a given excel file

    Args:
        filepath (Path): Path to the excel file containing module data

    Returns:
        (list[Module], list[str], list[str], set, set): A list of loaded 
        modules, a list of module group names, a list of semester IDs, a 
        set containing the IDs of any required modules not found in the 
        loaded modules list, a set containing the IDs of any mutually 
        excluded modules not found in the loaded modules list
    """
    module_data = pd.read_excel(filepath)
    return module_data

def get_formatted_module_data(module_data:pd.DataFrame):
    """Reformat the loaded dataframe containing module data into lists of required elements

    Args:
        module_data (pd.DataFrame): The loaded module data from a spreadsheet file

    Returns:
        (list[Module], list[str], list[str], set, set): A list of loaded 
        modules, a list of module group names, a list of semester IDs, a 
        set containing the IDs of any required modules not found in the 
        loaded modules list, a set containing the IDs of any mutually 
        excluded modules not found in the loaded modules list
    """
    # Keep track of any module IDs listed in the requirements or mutual exclusions but not found among the given modules
    required_modules_not_found = set()
    mutually_excluded_modules_not_found = set()

    # Create the module objects
    loaded_modules:dict[str, Module] = dict()
    for _, r in module_data.iterrows():
        m = Module(r.module_id, r.module_name, r.credits, r.semester, r.module_group, r.capacity, r.available_spaces, [], [])
        loaded_modules[r.module_id] = m

    # Add mutual exclusion and requirement references between the module objects
    for _, r in module_data.iterrows():    
        if not pd.isna(r.mutually_excluded_modules):
            mutually_excluded_module_ids = [s.strip() for s in r.mutually_excluded_modules.split(",") if len(s.strip()) > 0]
            for m in mutually_excluded_module_ids:
                if m in loaded_modules.keys():  
                    loaded_modules[r.module_id].add_mutual_exclusions([loaded_modules[m]])
                else:
                    mutually_excluded_modules_not_found.add(m)

        if not pd.isna(r.required_modules):
            required_module_ids = [s.strip() for s in r.required_modules.split(",") if len(s.strip()) > 0]
            for m in required_module_ids:
                if m in loaded_modules.keys(): 
                    loaded_modules[r.module_id].add_requirements([loaded_modules[m]])
                else:
                    required_modules_not_found.add(m)

    return list(loaded_modules.values()), list(module_data.module_group.unique()), list(module_data.semester.unique()), required_modules_not_found, mutually_excluded_modules_not_found


def validate_module_rankings_data(data:pd.DataFrame):
    errors = []
    required_columns = ["student_name", "student_id"]
    for c in required_columns:
        if not c in data.columns:
            errors += [f"Column '{c}' was not found in the module data file"]
    
    if ("student_id" in data.columns) and ("student_name" in data.columns):        
            for name in data.loc[(data['student_id'] == '') | pd.isna(data["student_id"]), 'student_name']:
                errors += [f"Student {name} has no listed student ID"]

    return errors 

def validate_module_group_preferences_data(data:pd.DataFrame):
    errors = []
    required_columns = ["student_name", "student_id"]
    for c in required_columns:
        if not c in data.columns:
            errors += [f"Column '{c}' was not found in the module data file"]
    
    if ("student_id" in data.columns) and ("student_name" in data.columns):        
            for name in data.loc[(data['student_id'] == '') | pd.isna(data["student_id"]), 'student_name']:
                errors += [f"Student {name} has no listed student ID"]

    return errors 

def load_module_rankings_data(module_preference_data_filepath:Path):
    return pd.read_excel(module_preference_data_filepath)

def load_module_group_preferences_data(module_group_preference_data_filepath:Path):
    return pd.read_excel(module_group_preference_data_filepath)

def load_students(module_rankings_data:pd.DataFrame, module_group_preference_data:pd.DataFrame, modules:list[Module]):
    """Load the student preferences data from two excel files

    Args:
        module_preference_data_filepath (Path): Path to the excel file containing module preference rankings
        module_group_preference_data_filepath (Path): Path to the excel file containing preferred numbers of modules per group
        modules (list[Module]): List of Module objects

    Returns:
        (list[Student], list[Student], list[Student], list[str]): A list of loaded Student objects, a list of students who did 
        not rank every module, a list of students with missing IDs, a list of module IDs not ranked by the students
    """
    # Load the excel files

    loaded_student_module_group_preferences:dict[str, dict[str, int]] = dict()
    loaded_students:dict[str, Student] = dict()

    student_to_uid = lambda r: f"{r.student_name.lower().strip().replace(" ", "")}_{r.student_id.strip().replace(" ", "")}" if not pd.isna(r.student_id) else f"{r.student_name.lower().strip().replace(" ", "")}_"

    # Keep track of any students who don't have rankings for all modules
    students_missing_ranks = []
    students_missing_ids = []

    # Get the group preferences for each student
    group_names = [col for col in module_group_preference_data.columns if col not in ["student_name", "student_id"]]
    for _, r in module_group_preference_data.iterrows():
        loaded_student_module_group_preferences[student_to_uid(r)] = dict(zip(group_names, [r[g] for g in group_names]))

    # Create the Student objects, containing module group preferences and within group ranks
    for _, r in module_rankings_data.iterrows():
        student_uid = student_to_uid(r)

        # Check if the student has a ranking value for every module
        all_modules_are_ranked = np.all([not pd.isna(r[m.module_id]) for m in modules if m.module_id in r.index])
        
        # Get the module-to-rank dictionary for this student
        module_rankings = dict(zip([m.module_id for m in modules if m.module_id in r.index], [(r[m.module_id] if not pd.isna(r[m.module_id]) else np.inf) for m in modules if m.module_id in r.index]))

        # Get the list of excluded modules for this student
        excluded_modules = [m.module_id for m in modules if m.module_id in r.excluded_modules] if not pd.isna(r.excluded_modules) else []

        # Create the Student object to contain this student's data
        student_id = r.student_id
        if pd.isna(r.student_id):
            students_missing_ids.append(r.student_name)
            student_id = r.student_name
        s = Student(r.student_name, student_id.strip(), loaded_student_module_group_preferences[student_uid], module_rankings, excluded_modules)
        loaded_students[student_uid] = s

        if not all_modules_are_ranked:
            students_missing_ranks.append(r.student_id)

    # List of modules not ranked by the students
    missing_modules = [m.module_id for m in modules if m.module_id not in module_rankings_data.columns]

    return list(loaded_students.values()), students_missing_ranks, students_missing_ids, missing_modules

def load_module_assignments(module_assignments_data_filepath:Path):
    module_assignments_data = pd.read_excel(module_assignments_data_filepath)
    return module_assignments_data

def validate_module_assignments_data(data:pd.DataFrame):
    errors = []
    required_columns = ["student_name", "student_id"]
    for c in required_columns:
        if not c in data.columns:
            errors += [f"Column '{c}' was not found in the module data file"]
    
    if ("student_id" in data.columns) and ("student_name" in data.columns):        
            for name in data.loc[(data['student_id'] == '') | pd.isna(data["student_id"]), 'student_name']:
                errors += [f"Student {name} has no listed student ID"]
    return errors 