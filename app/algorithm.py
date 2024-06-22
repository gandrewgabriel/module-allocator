from typing import Self
import numpy as np
import pandas as pd
import copy

class Module:    
    def __init__(self, module_id:str, module_name:str, credits:int, semester:int, group:str, total_spaces:int, available_spaces:int, mutual_exclusions:list[Self], requirements:list[Self]) -> None:
        self.module_id = module_id
        self.module_name = module_name
        self.credits = credits
        self.semester = semester
        self.group = group
        self.total_spaces = total_spaces
        self.available_spaces = available_spaces
        self.mutual_exclusions = mutual_exclusions
        self.requirements = requirements

    def __repr__(self) -> str:
        return f"Module: {self.module_id} | Cr:{self.credits} | S:{self.semester} | G:{self.group}"
    
    def add_mutual_exclusions(self, mutual_exclusions:list[Self]):
        self.mutual_exclusions = list(set(self.mutual_exclusions).union(mutual_exclusions))
        for module in mutual_exclusions:
            if self not in module.mutual_exclusions:
                module.add_mutual_exclusions([self])

    def add_requirements(self, requirements:list[Self]):
        self.requirements = list(set(self.requirements).union(requirements))

class Student:
    def __init__(self, name:str, id:str, preferred_modules_per_group:dict[str, int], module_rankings:dict[str, int], excluded_modules:list[str]):
        self.name = name
        self.id = id
        self.module_rankings_by_id = module_rankings
        self.preferred_modules_per_group = preferred_modules_per_group
        self.excluded_modules_by_id = excluded_modules

    def __repr__(self) -> str:
        return f"{self.name}"



#TODO: What object should keep tract of remaining spaces on each module? Probably the assigner rather than the module objects (which can be shared between assigners)
class ModuleAssigner:
    def __init__(self, students:list[Student], modules:list[Module], required_credits_per_student:int, max_credits_per_group:dict[str, int], max_credits_per_semester:dict[str, int], min_credits_per_group:dict[str, int], min_credits_per_semester:dict[str, int], random_seed:int):
        self._n_students = len(students)
        self._students = copy.deepcopy(students)
        self._student_ids = [s.id for s in self._students]
        self._modules = copy.deepcopy(modules)
        self._required_credits_per_student = required_credits_per_student
        self._unique_module_groups = list(set([m.group for m in self._modules]))
        self._unique_semesters = list(set([m.semester for m in self._modules]))
        self._grouped_modules = [[m for m in self._modules if m.group == group_label] for group_label in self._unique_module_groups]
        self._student_module_grouped_preferences = [np.array([[s.module_rankings_by_id[m.module_id] for m in module_group] for s in self._students]) for module_group in self._grouped_modules]
        self._student_module_group_credit_preferences = np.array([[s.preferred_modules_per_group[g] for g in self._unique_module_groups] for s in self._students])
        self._max_credits_per_group = [max_credits_per_group[g_id] for g_id in self._unique_module_groups]
        self._max_credits_per_semester = [max_credits_per_semester[i] for i in self._unique_semesters]
        self._min_credits_per_group = [min_credits_per_group[g_id] for g_id in self._unique_module_groups]
        self._min_credits_per_semester = [min_credits_per_semester[i] for i in self._unique_semesters]

        # list of N groups 2d arrays (one row per student, one column per module) containing assignments of students to each module in each group
        # TODO: Make it possible to load in how may credits the student has already been assigned
        self._student_assigned_credits = [np.zeros((len(self._students), len(self._grouped_modules[i])), dtype=np.int16) for i in range(len(self._unique_module_groups))]

        # Spaces remaining on each module
        #self._module_spaces_remaining = dict(zip(self._modules, map(lambda m: m.available_spaces, self._modules)))

        # Number of times the algorithm attempted to assign a student to each module
        self._module_spaces_excess_requests = dict(zip(self._modules, [0 for _ in range(len(self._modules))]))

        # Random state for choosing student permutations
        self._random_seed = random_seed
        self._rs = np.random.RandomState(random_seed)

    def set_loaded_module_assignments(self, data:pd.DataFrame):
        """Load the previously assigned modules for each student
        from the given dataframe

        Args:
            data (pd.DataFrame): A data frame containing a column of student IDs, and columns for each module, where a non-zero entry in the latter columns indicates that the student was assigned to that module
        """

        for s_idx, s in enumerate(self._students):
            student_data = data[(data.student_id == s.id)]
            for mg_idx, mg in enumerate(self._grouped_modules):
                for m_idx, m in enumerate(mg):
                    if student_data[m.module_id].values[0] > 0:
                        self._student_assigned_credits[mg_idx][s_idx][m_idx] = m.credits



    def get_module_dataframe(self):
        """Get a Pandas DataFrame containing the module metadata (ids, names, capacity, etc),
        and the number of unallocated spaces remaining on each module.

        Returns:
            pd.DataFrame: The module metadata
        """
        data = dict()
        data["module_id"] = []
        data["module_name"] = []
        data["module_group"] = []
        data["semester"] = []
        data["credits"] = []
        data["capacity"] = []
        data["available_spaces"] = []
        data["required_modules"] = []
        data["mutually_excluded_modules"] = []

        for module in self._modules:
            data["module_id"] += [module.module_id]
            data["module_name"] += [module.module_name]
            data["module_group"] += [module.group]
            data["semester"] += [module.semester]
            data["credits"] += [module.credits]
            data["capacity"] += [module.total_spaces]
            data["available_spaces"] += [module.available_spaces]
            data["required_modules"] += [",".join([m.module_id for m in module.requirements])]
            data["mutually_excluded_modules"] += [",".join([m.module_id for m in module.mutual_exclusions])]

        return pd.DataFrame(data)

    def get_assigned_credits_totals(self):
        """Get the total number of credits assigned to each student

        Returns:
            np.ndarray: An array of integers representing the total numbers of credits assigned to each student
        """
        return np.sum(np.array(list(map(lambda a: np.sum(a, axis=1), self._student_assigned_credits))).T, axis=1)
    

    def get_assigned_modules(self, selected_student_id:str):
        """Get a list of the Module objects which have been assigned to
        the student with the given ID

        Args:
            selected_student_id (str): ID of the student whose assigned modules to return

        Returns:
            List[Module]: A list of references to the modules assigned to the given student
        """
        s_idx = self._student_ids.index(selected_student_id)
        assigned_modules:list[Module] = []
        for g_idx, group in enumerate(self._student_assigned_credits):
            for m_idx in np.nonzero(group[s_idx])[0]:
                assigned_modules += [self._grouped_modules[g_idx][m_idx]]
        return assigned_modules
    
    def get_all_assigned_modules(self):
        student_names = [s.name for s in self._students]
        student_ids = [s.id for s in self._students]

        names_ids_df = pd.DataFrame({"student_name":student_names, "student_id":student_ids})
        student_module_group_preferences_df = pd.DataFrame([s.preferred_modules_per_group for s in self._students])
        module_allocations_df = pd.DataFrame(columns=[m.module_id for m in self._modules])        
        
        for s_idx, s in enumerate(self._students):
            assigned_modules = self.get_assigned_modules(s.id)
            new_row = {m.module_id: s.module_rankings_by_id[m.module_id] if m in assigned_modules else 0 for m in self._modules}
            module_allocations_df.loc[s_idx] = new_row

        return pd.concat([names_ids_df, student_module_group_preferences_df, module_allocations_df], axis=1)
    
    def get_assigned_module_students(self):
        module_ids = []
        assigned_student_dfs = []
        for m in self._modules:
            students_for_current_module:list[Student] = []
            for s in self._students:
                assigned_modules = self.get_assigned_modules(s.id)
                if m in assigned_modules:
                    students_for_current_module.append(s)
            
            df = pd.DataFrame({"student_name":[s.name for s in students_for_current_module], "student_id":[s.id for s in students_for_current_module]})
            module_ids.append(m.module_id)
            assigned_student_dfs.append(df)

        return module_ids, assigned_student_dfs

    def get_assignment_satisfaction_scores(self):
        """Get the per-participant, per-module-group satisfaction scores.
        The satisfaction score is a number in the range [0, 1], where 1
        corresponds to the case where the student has been assigned their
        most preferred modules in that group and 0 corresponds to the 
        case where they have been assigned their least preferred modules.
        The students' stated preferences for numbers of modules per
        group are not accounted for by this measure.

        Returns:
            np.ndarray: An array of shape (# students, # module groups) containing satisfaction scores
        """
        modules_per_group = np.zeros(len(self._unique_module_groups))
        for m in self._modules:
            g_idx = self._unique_module_groups.index(m.group)
            modules_per_group[g_idx] += 1

        scores = []
        best = []
        worst = []
        for s in self._students:
            per_group_assignment_counts = np.zeros(len(self._unique_module_groups))
            ideal_per_group_pref_scores = np.zeros(len(self._unique_module_groups))
            worst_per_group_pref_scores = np.zeros(len(self._unique_module_groups))
            per_group_pref_scores = np.zeros(len(self._unique_module_groups))
            assigned_modules = self.get_assigned_modules(s.id)

            for m in assigned_modules:
                g_idx = self._unique_module_groups.index(m.group)
                per_group_pref_scores[g_idx] += s.module_rankings_by_id[m.module_id]
                per_group_assignment_counts[g_idx] += 1

            for g_id in self._unique_module_groups:
                g_idx = self._unique_module_groups.index(g_id)
                ideal_per_group_pref_scores[g_idx] = np.sum(np.arange(per_group_assignment_counts[g_idx]) + 1)
                worst_per_group_pref_scores[g_idx] = np.sum(np.arange(modules_per_group[g_idx] - per_group_assignment_counts[g_idx], modules_per_group[g_idx]) + 1)

            scores += [per_group_pref_scores]
            best += [ideal_per_group_pref_scores]
            worst += [worst_per_group_pref_scores]      

        return 1 - ((np.stack(scores) - np.stack(best)) / (np.stack(worst) - np.stack(best)))

    def get_excess_module_requests(self):
        module_ids = [m.module_id for m in self._modules]
        module_names = [m.module_name for m in self._modules]
        excess_requests = [self._module_spaces_excess_requests[m] for m in self._modules]
        proportion_overrequested = [self._module_spaces_excess_requests[m] / m.total_spaces for m in self._modules]
        return pd.DataFrame({"module_id":module_ids, "module_name":module_names, "excess_requests":excess_requests, "proportion_overrequested":proportion_overrequested})

    def assignment_satisfies_minimum_credits_per_group(self):
        """
        Returns:
            boolean: True iff the assignment of students to modules meets the minimum number of credits per module group for all students
        """
        return np.array(list(map(lambda a: np.sum(a, axis=1), self._student_assigned_credits))).T >= self._min_credits_per_group
    
    def assignment_satisfies_minimum_credits_per_semester(self):
        """        
        Returns:
            boolean: True iff the assignment of students to modules meets the minimum number of credits per semester for all students
        """
        credits_per_semester = np.stack([np.sum(np.stack([np.sum(np.stack([self._student_assigned_credits[g_idx][:, m_idx] for m_idx, m in enumerate(g) if m.semester == s]), axis=0) for g_idx, g in enumerate(self._grouped_modules)]), axis=0) for s in self._unique_semesters]).T
        return credits_per_semester >= self._min_credits_per_semester

    def log(self, message):
        print(message)

    def run_assignment_round(self, allow_least_preferred_modules:bool = True):
        

        """Run one round of the assignment algorithm.
        This may assign more than one module to each participant, if 
        the module to be assigned has other modules as requirements.
        If there are no modules available which satisfy the constraints
        for a given student then no module will be assigned to them.

        Returns:
            List[dict[str, boolean]]: A list of dictionaries giving 
            information about constraints that were not satisfied while 
            trying to assign a module to each participant.
        """

        # How many credits has each student been assigned in each module group
        assigned_credits_total = np.array(list(map(lambda a: np.sum(a, axis=1), self._student_assigned_credits))).T

        # Which module group is furthest from satisfying the students' preferred number of credits for that group
        next_assignment_group_idxs = np.argsort(assigned_credits_total - self._student_module_group_credit_preferences, axis=1)
       
        # Select a random order in which to let students "pick" a module
        choice_order = self._rs.permutation(self._n_students)

        # self.log(assigned_credits_total)
        # self.log("|||||")

        # Keep track of which modules each student has already "requested" during allocation
        requested_modules = dict(zip(self._students, [[] for _ in self._students]))

        result_trace = []
        # For each participant in a random order
        for student_idx in choice_order:

            # If the current student has not got enough assigned module credits yet...
            if np.sum(assigned_credits_total[student_idx]) < self._required_credits_per_student:

                modules_assigned = False

                # Select the group of modules needing a new assignment for this participant.
                # If we can't allocate a module in the preferred group, try the next most preferred group.
                for group_idx in next_assignment_group_idxs[student_idx]:

                    # The module preference rankings of the current student for the current module group 
                    current_student_group_module_prefs = self._student_module_grouped_preferences[group_idx][student_idx]

                    # For each module in descending order of preference (i.e. increasing preference value)...
                    for module_idx in np.argsort(current_student_group_module_prefs):

                        student_assigned_modules:list[Module] = self.get_assigned_modules(self._student_ids[student_idx])

                        student_assigned_credits_per_semester = np.zeros(len(self._max_credits_per_semester))
                        for m in student_assigned_modules:                       
                            student_assigned_credits_per_semester[self._unique_semesters.index(m.semester)] += m.credits

                        # Select this student's most preferred module in the current module group
                        module:Module = self._grouped_modules[group_idx][module_idx]
                        
                        # Select the module and its requirements that have not yet been assigned to this student
                        modules_to_assign = set(module.requirements + [module]).difference(student_assigned_modules)

                        if len(modules_to_assign) > 0:                    

                            requested_credits_per_group = np.zeros(len(self._max_credits_per_group))
                            for m in modules_to_assign:
                                requested_credits_per_group[self._unique_module_groups.index(m.group)] += m.credits

                            requested_credits_per_semester = np.zeros(len(self._max_credits_per_semester))
                            for m in modules_to_assign:                       
                                requested_credits_per_semester[self._unique_semesters.index(m.semester)] += m.credits
                            
                            # If both the selected module and its requirements have space remaining for new students...
                            modules_have_space_remaining = np.all([m.available_spaces > 0 for m in modules_to_assign])
                            
                            # If neither the selected module nor its requirements are mutually excluded by already assigned modules...                
                            current_student_mutual_exclusions = [ex_m for m in student_assigned_modules for ex_m in m.mutual_exclusions]
                            modules_not_excluded = set(modules_to_assign).isdisjoint(current_student_mutual_exclusions)

                            # If the selected module and its requirements are not in the list of modules specifically excluded by this student...
                            modules_not_excluded_by_student = set(map(lambda m: m.module_id, modules_to_assign)).isdisjoint(self._students[student_idx].excluded_modules_by_id)

                            # If the selected module and its requirements will not give the student too many credits in each group...
                            requested_credits_not_too_many_per_group = np.all(assigned_credits_total[student_idx] + requested_credits_per_group <= self._max_credits_per_group)

                            # If the selected module and its requirements will not give the student too many credits in total, across all groups...
                            requested_credits_not_too_many_total = np.sum(assigned_credits_total[student_idx] + requested_credits_per_group) <= self._required_credits_per_student

                            # If the selected module and its requirements will not give the student too many credits in one semester...
                            requested_credits_per_semester_not_too_many = np.all(student_assigned_credits_per_semester + requested_credits_per_semester <= self._max_credits_per_semester)

                            # If one of the selected modules has the lowest possible preference (i.e. largest preference rating) in its module group
                            least_preferred_module_selected = np.any([current_student_group_module_prefs[self._grouped_modules[group_idx].index(m)] == np.max(current_student_group_module_prefs) for m in modules_to_assign])
                            preferences_okay = (not least_preferred_module_selected) or (least_preferred_module_selected and allow_least_preferred_modules)            

                            # Keep track of how many excess requests (beyond module capacity) each module had during allocation, counting each student only once
                            if not modules_have_space_remaining:
                                if not m in requested_modules[self._students[student_idx]]:
                                    self._module_spaces_excess_requests[m] = self._module_spaces_excess_requests[m] + 1
                                    requested_modules[self._students[student_idx]] = requested_modules[self._students[student_idx]] + [m]

                            # if not modules_have_space_remaining:
                            #     self.log("Assignment pass failed: Requested modules have no spaces remaining")
                            #     continue

                            # if not modules_not_excluded:
                            #     self.log("Assignment pass failed: Mutually excluded modules were requested")
                            #     continue

                            # if not modules_not_excluded_by_student:
                            #     self.log("Assignment pass failed: Student excluded modules were requested")
                            #     continue

                            # if not requested_credits_not_too_many_per_group:
                            #     self.log("Assignment pass failed: Requested modules exceeded per group credit maximum")
                            #     continue

                            # if not requested_credits_not_too_many_total:
                            #     self.log("Assignment pass failed: Requested modules exceeded total credit maximum")
                            #     continue

                            # if not requested_credits_per_semester_not_too_many:
                            #     self.log("Assignment pass failed: Requested modules exceeded per semester credit maximum")
                            #     continue

                            # if not preferences_okay:
                            #     self.log("Assignment pass failed: Requested modules included lowest-ranked module for the current student")
                            #     continue


                            # Assign the module and its requirements to the student
                            if modules_have_space_remaining and modules_not_excluded and modules_not_excluded_by_student and requested_credits_not_too_many_per_group and requested_credits_not_too_many_total and requested_credits_per_semester_not_too_many and preferences_okay:
                                for m in modules_to_assign:
                                    g_idx = self._unique_module_groups.index(m.group)
                                    m_idx = self._grouped_modules[g_idx].index(m)                                    
                                    self._student_assigned_credits[g_idx][student_idx][m_idx] = m.credits
                                    m.available_spaces -= 1
                                    #self._module_spaces_remaining[m] = self._module_spaces_remaining[m] - 1
                                    #self._modules[self._modules.index(m)].available_spaces -= 1
                                    assigned_credits_total[student_idx][g_idx] += m.credits
                                    modules_assigned = True
                                break
                        
                    if modules_assigned:
                        break
                    
                if not modules_assigned:
                    result_trace += [dict(zip(["student_id",
                                              "modules_have_space_remaining", 
                                              "modules_not_excluded", 
                                              "requested_credits_not_too_many_per_group", 
                                              "requested_credits_not_too_many_total", 
                                              "requested_credits_per_semester_not_too_many",
                                              "preferences_okay"],
                                             [self._student_ids[student_idx],
                                             modules_have_space_remaining, 
                                             modules_not_excluded, 
                                             requested_credits_not_too_many_per_group, 
                                             requested_credits_not_too_many_total, 
                                             requested_credits_per_semester_not_too_many,
                                             preferences_okay]))]


        return result_trace