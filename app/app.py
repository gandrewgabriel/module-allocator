from pathlib import Path
from zipfile import ZipFile
from htmltools import HTML
import numpy as np
import pandas as pd
from shiny.express import ui, input, render
from shiny import reactive
from algorithm import ModuleAssigner
from custom_widgets import input_file_area
from data_loading import (
    check_ranking_and_group_ids_match,
    check_sufficient_module_spaces,
    get_formatted_module_data,
    load_module_assignments,
    load_module_data,
    load_module_rankings_data,
    load_students,
    validate_module_assignments_data,
    validate_module_data,
    validate_module_group_preferences_data,
    validate_module_rankings_data,
)
from io import BytesIO
from faicons import icon_svg

APP_VERSION = "0.2.0"

BASE_RANDOM_SEED = 8194761

MAX_SIZE = 50000
ACCEPTED_FILETYPES = [".csv"]

module_data = reactive.value()
module_dataframe = reactive.value()
module_data_error = reactive.value()
_ = module_data_error.set(False)
module_groups_data = reactive.value()
semesters_data = reactive.value()

required_credits_per_student_data = reactive.value()
module_groups_data_mins = reactive.value()
module_groups_data_maxs = reactive.value()
semesters_data_mins = reactive.value()
semesters_data_maxs = reactive.value()

# If the students request more modules in any group than the total capacity in
# that group, we have to relax the constraint of assigning students their
# preferred number of modules per group
module_group_overrequest = reactive.value()
_ = module_group_overrequest.set(False)

student_module_rankings = reactive.value()
module_rankings_error = reactive.value()
_ = module_rankings_error.set(False)
student_group_preferences = reactive.value()
student_group_preferences_error = reactive.value()
_ = student_group_preferences_error.set(False)
student_previous_module_allocations = reactive.value()
student_previous_module_allocations_error = reactive.value()
_ = student_previous_module_allocations_error.set(False)
student_data = reactive.value()

best_assignment_module_assigner_data = reactive.value()
best_assignment_data = reactive.value()
excess_module_requests_data = reactive.value()
module_allocation_state_data = reactive.value()


def create_error_modal(message: str):
    return ui.modal(HTML(message), title="Error", easy_close=True)


ui.include_css(Path(__file__).parent / "styles.css")
ui.head_content(ui.tags.title(f"Module Allocator {APP_VERSION}"))

@render.express
def _():
    ui.panel_title(f"Module Allocator {APP_VERSION}")

    with ui.navset_underline(id="tab"):
        # ui.card_header("Input Data")
        
        with ui.nav_panel(
            "Modules",
            icon=(
                icon_svg("check")
                if module_data.is_set() and not module_data_error.get() == True
                else (
                    icon_svg("exclamation")
                    if module_data_error.get() == True
                    else None
                )
            ),
        ):
                if not module_data.is_set():
                    input_file_area(
                        "modules_file",
                        "Module data file",
                        multiple=False,
                        accept=ACCEPTED_FILETYPES,
                    )
                else:
                    with ui.card():
                        ui.card_header("Module Constraints")

                        ui.input_action_button(
                            "reset_module_data",
                            "Reset Module Data",
                            icon=icon_svg("trash"),
                        )

                        with ui.card():
                            ui.card_header("Required Credits Per Student")
                            ui.input_numeric(
                                "required_credits_per_student",
                                "Required Credits Per Student",
                                1,
                                min=1,
                                max=1000,
                            )

                        with ui.layout_columns(col_widths=[6, 6]):
                            with ui.card():
                                ui.card_header("Min Credits Per Module Group")
                                [
                                    ui.input_numeric(
                                        f"min_credits_module_group_{i}",
                                        x,
                                        1,
                                        min=1,
                                        max=1000,
                                    )
                                    for i, x in enumerate(module_groups_data())
                                ]
                            with ui.card():
                                ui.card_header("Max Credits Per Module Group")
                                [
                                    ui.input_numeric(
                                        f"max_credits_module_group_{i}",
                                        x,
                                        1,
                                        min=1,
                                        max=1000,
                                    )
                                    for i, x in enumerate(module_groups_data())
                                ]

                        with ui.layout_columns(col_widths=[6, 6]):
                            with ui.card():
                                ui.card_header("Min Credits Per Semester")
                                [
                                    ui.input_numeric(
                                        f"min_credits_semester_{i}",
                                        str(x),
                                        1,
                                        min=1,
                                        max=1000,
                                    )
                                    for i, x in enumerate(semesters_data())
                                ]
                            with ui.card():
                                ui.card_header("Max Credits Per Semester")
                                [
                                    ui.input_numeric(
                                        f"max_credits_semester_{i}",
                                        str(x),
                                        1,
                                        min=1,
                                        max=1000,
                                    )
                                    for i, x in enumerate(semesters_data())
                                ]

                # with ui.popover():
                #     icon("circle-info")
                #     "Spreadsheet containing module IDs, names, semesters, group names, and capacities"

        with ui.nav_panel(
            "Rankings",
            icon=(
                icon_svg("check")
                if student_module_rankings.is_set()
                and not module_rankings_error.get() == True
                else (
                    icon_svg("exclamation")
                    if module_rankings_error.get() == True
                    else None
                )
            ),
        ):

            if not student_module_rankings.is_set():
                input_file_area(
                    "student_module_rankings_file",
                    "Student module rankings file",
                    multiple=False,
                    accept=ACCEPTED_FILETYPES,
                )
            else:
                with ui.card():
                    ui.input_action_button(
                        "reset_module_rankings_data",
                        "Reset Module Rankings Data",
                        icon=icon_svg("trash"),
                    )

            # with ui.popover():
            #     icon("circle-info")
            #     "Spreadsheet containing student IDs, names, and (for each student) a within-group preference ranking for each module"

        with ui.nav_panel(
            "Group Preferences",
            icon=(
                icon_svg("check")
                if student_group_preferences.is_set()
                and not student_group_preferences_error.get() == True
                else (
                    icon_svg("exclamation")
                    if student_group_preferences_error.get() == True
                    else None
                )
            ),
        ):
            if not student_group_preferences.is_set():
                input_file_area(
                    "student_group_preferences_file",
                    "Student module group preferences file",
                    multiple=False,
                    accept=ACCEPTED_FILETYPES,
                )
            else:
                with ui.card():
                    ui.input_action_button(
                        "reset_group_preferences_data",
                        "Reset Group Preferences Data",
                        icon=icon_svg("trash"),
                    )
            # with ui.popover():
            #     icon("circle-info")
            #     "Spreadsheet containing student IDs, names, and (for each student) a preferred number of modules per group"

        with ui.nav_panel(
            "Prior Allocations",
            icon=(
                icon_svg("check")
                if student_previous_module_allocations.is_set()
                and not student_previous_module_allocations_error.get() == True
                else (
                    icon_svg("exclamation")
                    if student_previous_module_allocations_error.get() == True
                    else None
                )
            ),
        ):
            if not student_previous_module_allocations.is_set():
                input_file_area(
                    "student_previous_module_allocations_file",
                    "Existing student module allocations file (Optional)",
                    multiple=False,
                    accept=ACCEPTED_FILETYPES,
                )
            else:
                with ui.card():
                    ui.input_action_button(
                        "reset_prior_allocations_data",
                        "Reset Prior Allocations Data",
                        icon=icon_svg("trash"),
                    )

            # with ui.popover():
            #     icon("circle-info")
            #     "Spreadsheet containing a student_id column and columns for each module ID, with non-zero entries in columns to which each student (row) has been assigned"

        ui.nav_spacer()

        with ui.nav_panel("Allocation", icon=icon_svg("play")):
            with ui.card():
                ui.card_header("Module Assignment Results")
                with ui.layout_columns(col_widths=[3, 9]):
                    with ui.card():
                        ui.input_numeric(
                            "early_stop_number",
                            "Stop After N Modules Per Student",
                            3,
                            min=1,
                            max=100,
                        )
                        ui.input_checkbox(
                            "validate_constraints",
                            "Post-check module/credit constraints",
                            False,
                        )
                        ui.input_numeric(
                            "custom_random_seed",
                            "Random Seed",
                            BASE_RANDOM_SEED,
                            min=10000,
                            max=999999999,
                        )
                        ui.input_numeric(
                            "assignment_runs",
                            "Random Search Repetitions",
                            10,
                            min=1,
                            max=250,
                        )
                        ui.input_action_button("run", "Run Assignment")

                        @render.ui
                        def download_button():
                            return (
                                render.download(
                                    download, filename="assigned_modules.zip"
                                )
                                if best_assignment_module_assigner_data.is_set()
                                else None
                            )

                    with ui.card():
                        with ui.navset_pill(
                            id="module_assignment_results_tabset"
                        ):
                            with ui.nav_panel("Assigned Modules"):

                                @render.data_frame
                                def assignment_df():
                                    return render.DataGrid(
                                        best_assignment_data.get()
                                    )

                            with ui.nav_panel("Over-Requested Modules"):

                                @render.data_frame
                                def excess_module_requests_df():
                                    return render.DataGrid(
                                        excess_module_requests_data.get()
                                    )


def load_student_data():
    student_data.set(None)
    try:

        missing_from_rankings, missing_from_group_prefs = check_ranking_and_group_ids_match(student_module_rankings.get(), student_group_preferences.get())

        if len(missing_from_rankings) > 0:
            ui.modal_show(
                    create_error_modal("\n".join([f"<p>Student ID '{str(e)}' is present in the Group Preferences file, but missing from the Rankings file</p>" for e in missing_from_rankings]))
                )
            reset_module_rankings_data()            
            
        if len(missing_from_group_prefs) > 0:
            ui.modal_show(
                    create_error_modal("\n".join([f"<p>Student ID '{str(e)}' is present in the Rankings file, but missing from the Group Preferences file</p>" for e in missing_from_group_prefs]))
                )            
            reset_group_preferences_data()
        
        if len(missing_from_rankings) > 0 or len(missing_from_group_prefs) > 0:
            return
        

        # Do the students request more modules in a given group than the total capacity of that group?
        warnings = []
        module_space_check_results = check_sufficient_module_spaces(module_dataframe.get(), student_group_preferences.get())
        if len(module_space_check_results) > 0:

            module_group_overrequest.set(True)

            for (group_id, total_requested_spaces, total_available_spaces) in module_space_check_results:
                if (total_requested_spaces > total_available_spaces):
                    warnings += [f"Students requested {total_requested_spaces} module spaces in group '{group_id}', but only {total_available_spaces} are available."]
            warnings += ["Module allocation may still work, but some students will be assigned fewer modules in these groups than they requested."]
            
            ui.modal_show(create_error_modal("\n".join([f"<p>{w}</p>" for w in warnings])))

    
        students, students_missing_ranks, students_missing_ids, missing_modules = (
            load_students(
                student_module_rankings.get(),
                student_group_preferences.get(),
                module_data.get(),
            )
        )
        student_data.set(students)

        errors = []

        for m in missing_modules:
            errors += [f"Module '{m}' is missing from the Rankings file"]

        for s in students_missing_ranks:
            errors += [f"Student with ID '{s}' has module preference rankings missing in the Rankings file"]
       
        if len(errors) > 0:
            reset_module_rankings_data()            
            ui.modal_show(create_error_modal("\n".join([f"<p>{e}</p>" for e in errors])))
            return
            

    except Exception as e:
        print(e)
        ui.modal_show(
            create_error_modal(
                "There was an error loading data from the student module preference files. Please ensure their content is in the correct format and try again."
            )
        )


@reactive.effect
@reactive.event(input.reset_module_data)
def _():
    module_data.set(None)
    module_data.unset()


@reactive.effect
@reactive.event(input.reset_group_preferences_data)
def _():
    reset_group_preferences_data()
def reset_group_preferences_data():
    student_group_preferences.set(None)
    student_group_preferences.unset()
    student_group_preferences_error.set(False)
    student_data.unset()


@reactive.effect
@reactive.event(input.reset_module_rankings_data)
def _():
    reset_module_rankings_data()
def reset_module_rankings_data():
    student_module_rankings.set(None)
    student_module_rankings.unset()
    module_rankings_error.set(False)
    student_data.unset()


@reactive.effect
@reactive.event(input.reset_prior_allocations_data)
def _():
    student_previous_module_allocations.set(None)
    student_previous_module_allocations.unset()


@reactive.effect
@reactive.event(input.modules_file)
def file_content():
    persist_module_allocation_settings()
    modules_file_info = input.modules_file()[0]
    if not modules_file_info:
        return

    try:
        module_df = load_module_data(Path(modules_file_info["datapath"]))
        errors = validate_module_data(module_df)
        if len(errors) > 0:
            ui.modal_show(
                create_error_modal("\n".join([f"<p>{e}</p>" for e in errors]))
            )
            module_data_error.set(True)
            return
        (
            modules,
            module_groups,
            semesters,
            required_modules_not_found,
            mutually_excluded_modules_not_found,
        ) = get_formatted_module_data(module_df)
        module_dataframe.set(module_df)
        module_data.set(modules)
        module_groups_data.set(module_groups)
        semesters_data.set(semesters)
        module_data_error.set(False)
        reload_module_allocation_settings()
    except Exception as e:
        print(e)
        ui.modal_show(
            create_error_modal(
                "There was an error loading data from the module file. Please ensure its content is in the correct format and try again."
            )
        )


@reactive.effect
@reactive.event(input.student_module_rankings_file)
def file_content():
    persist_module_allocation_settings()
    student_module_rankings_file_info = input.student_module_rankings_file()[0]
    if not student_module_rankings_file_info:
        return
    try:
        module_rankings_data = load_module_rankings_data(
            student_module_rankings_file_info["datapath"]
        )
        errors = validate_module_rankings_data(module_rankings_data)

        if len(errors) > 0:
            ui.modal_show(
                create_error_modal("\n".join([f"<p>{e}</p>" for e in errors]))
            )
            module_rankings_error.set(True)
            return
        student_module_rankings.set(module_rankings_data)
        if student_group_preferences.is_set() and module_data.is_set():
            load_student_data()
        module_rankings_error.set(False)
        reload_module_allocation_settings()
    except Exception as e:
        print(e)
        ui.modal_show(
            create_error_modal(
                "There was an error loading data from the module rankings file. Please ensure its content is in the correct format and try again."
            )
        )


@reactive.effect
@reactive.event(input.student_group_preferences_file)
def file_content():
    persist_module_allocation_settings()
    student_group_preferences_file_info = input.student_group_preferences_file()[0]
    if not student_group_preferences_file_info:
        return
    try:
        student_group_preferences_data = load_module_rankings_data(
            student_group_preferences_file_info["datapath"]
        )
        errors = validate_module_group_preferences_data(student_group_preferences_data)

        if len(errors) > 0:
            ui.modal_show(
                create_error_modal("\n".join([f"<p>{e}</p>" for e in errors]))
            )
            student_group_preferences_error.set(True)
            return
        student_group_preferences.set(student_group_preferences_data)
        if student_module_rankings.is_set() and module_data.is_set():
            load_student_data()
        student_group_preferences_error.set(False)
        reload_module_allocation_settings()
    except Exception as e:
        print(e)
        ui.modal_show(
            create_error_modal(
                "There was an error loading data from the module group preferences file. Please ensure its content is in the correct format and try again."
            )
        )


@reactive.effect
@reactive.event(input.student_previous_module_allocations_file)
def file_content():

    persist_module_allocation_settings()

    student_previous_module_allocations_file_info = (
        input.student_previous_module_allocations_file()[0]
    )
    if not student_previous_module_allocations_file_info:
        return
    try:
        student_previous_assignments_data = load_module_assignments(
            student_previous_module_allocations_file_info["datapath"]
        )
        errors = validate_module_assignments_data(student_previous_assignments_data)

        if len(errors) > 0:
            ui.modal_show(
                create_error_modal("\n".join([f"<p>{e}</p>" for e in errors]))
            )
            student_previous_module_allocations_error.set(True)
            return
        
        student_previous_assignments_data["student_id"] = student_previous_assignments_data["student_id"].astype(str)
        student_previous_module_allocations.set(student_previous_assignments_data)
        student_previous_module_allocations_error.set(False)
        reload_module_allocation_settings()
    except Exception as e:
        print(e)
        ui.modal_show(
            create_error_modal(
                "There was an error loading data from the previous module assignments file. Please ensure its content is in the correct format and try again."
            )
        )


@reactive.effect
@reactive.event(input.run)
async def show_message():
    module_data_set = module_data.is_set()
    student_module_rankings_set = student_module_rankings.is_set()
    student_group_preferences_set = student_group_preferences.is_set()

    m1 = "" if module_data_set else "<li>Module information"
    m2 = "" if student_module_rankings_set else "<li>Student module rankings"
    m3 = "" if student_group_preferences_set else "<li>Student module group preferences"
    message = "Please provide the following data before running module assignment: <ul>"
    for m in [m1, m2, m3]:
        if m != "":
            message += m

    if (
        not module_data_set
        and not student_module_rankings_set
        and not student_group_preferences_set
    ):
        m = ui.modal(
            HTML(message),
            easy_close=True,
            footer=None,
        )
        ui.modal_show(m)

    else:
        assignment_repetitions = input["assignment_runs"].get()
        best_assignment = None

        loaded_module_assignments = None
        if student_previous_module_allocations.is_set():
            loaded_module_assignments = student_previous_module_allocations.get()

        with ui.Progress(min=1, max=assignment_repetitions) as p:
            for r in range(assignment_repetitions):
                p.set(
                    message="Running module assignment",
                    detail=f"{r+1} of {assignment_repetitions}",
                )
                best_assignment = run_assignments(
                    r,
                    best_assignment,
                    input["early_stop_number"].get(),
                    input["validate_constraints"].get(),
                    loaded_module_assignments,
                )
                p.set(r)

        if not best_assignment is None:
            best_assignment_module_assigner_data.set(best_assignment)
            best_assignment_data.set(best_assignment.get_all_assigned_modules())
            excess_module_requests_data.set(
                best_assignment.get_excess_module_requests().sort_values(
                    "excess_requests", ascending=False
                )
            )
            module_allocation_state_data.set(best_assignment.get_module_dataframe())

        else:
            ui.notification_show(
                "No assignments satisfying the provided constraints were found. Please check the constraints and try again.",
                type="error",
                duration=None,
            )


def download():
    if best_assignment_module_assigner_data.is_set():
        module_assignments: ModuleAssigner = best_assignment_module_assigner_data.get()
        module_ids, assigned_students_data = (
            module_assignments.get_assigned_module_students()
        )
        zip_file = BytesIO()
        with ZipFile(zip_file, "w") as zf:
            # Write the csv files containing student IDs assigned to each module
            for m_idx, m in enumerate(module_ids):
                b = BytesIO()
                assigned_students_data[m_idx].to_csv(b, index=False, header=True)
                zf.writestr(f"{m}.csv", b.getvalue())

            # Write the summary of all module assignments for all students to an csv file
            b_assignment_summary = BytesIO()
            best_assignment_data.get().to_csv(
                b_assignment_summary, index=False, header=True
            )
            zf.writestr(
                f"module_assignment_summary.csv", b_assignment_summary.getvalue()
            )

            #
            best_module_assigner = best_assignment_module_assigner_data.get()
            semester_min_credits_satisfied, semester_labels = best_module_assigner.assignment_satisfies_minimum_credits_per_semester()
            df_semester_min = pd.DataFrame(semester_min_credits_satisfied, columns=[f"min_credits_per_semester_satisfied_{l}" for l in semester_labels])

            semester_max_credits_satisfied, semester_labels = best_module_assigner.assignment_satisfies_maximum_credits_per_semester()
            df_semester_max = pd.DataFrame(semester_max_credits_satisfied, columns=[f"max_credits_per_semester_not_exceeded_{l}" for l in semester_labels])

            group_min_credits_satisfield, group_labels = best_module_assigner.assignment_satisfies_minimum_credits_per_group()
            df_group_min = pd.DataFrame(group_min_credits_satisfield, columns=[f"min_credits_per_group_satisfied_{l}" for l in group_labels])

            group_max_credits_satisfield, group_labels = best_module_assigner.assignment_satisfies_maximum_credits_per_group()
            df_group_max = pd.DataFrame(group_max_credits_satisfield, columns=[f"max_credits_per_group_not_exceeded_{l}" for l in group_labels])

            total_credits_satisfied = best_module_assigner.get_assigned_credits_totals() == best_module_assigner._required_credits_per_student
            df_total_credits = pd.DataFrame(total_credits_satisfied, columns=["required_credits_total_satisfied"])

            student_list_df = best_module_assigner.get_students_list()

            constraints_df = pd.concat([student_list_df, df_semester_min, df_semester_max, df_group_min, df_group_max, df_total_credits], axis=1)
            b_constraints_summary = BytesIO()
            constraints_df.to_csv(
                b_constraints_summary, index=False, header=True
            )
            zf.writestr(
                f"constraints_summary.csv", b_constraints_summary.getvalue()
            )

            # Write data on excess module requests to an csv file
            b_over_requested_modules = BytesIO()
            excess_module_requests_data.get().to_csv(
                b_over_requested_modules, index=False, header=True
            )
            zf.writestr(
                f"excess_module_requests.csv", b_over_requested_modules.getvalue()
            )

            # Write the list of modules and associated metadata (including remaining spaces on each module) back to an csv file
            b_module_allocation_state = BytesIO()
            module_allocation_state_data.get().to_csv(
                b_module_allocation_state, index=False, header=True
            )
            zf.writestr(f"module_metadata.csv", b_module_allocation_state.getvalue())

        yield zip_file.getvalue()


def persist_module_allocation_settings():
    """Store the manually inputted module allocation settings, so that we can restore
    them when the UI changes.
    """
    if module_data.is_set():
        required_credits_per_student_data.set(input.required_credits_per_student.get())
        module_groups_data_maxs.set([
                        input[f"max_credits_module_group_{i}"].get()
                        for i, _ in enumerate(module_groups_data())
                    ])
        module_groups_data_mins.set([
                        input[f"min_credits_module_group_{i}"].get()
                        for i, _ in enumerate(module_groups_data())
                    ])
        semesters_data_maxs.set([
                        input[f"max_credits_semester_{i}"].get()
                        for i, _ in enumerate(semesters_data())
                    ])
        semesters_data_mins.set([
                        input[f"min_credits_semester_{i}"].get()
                        for i, _ in enumerate(semesters_data())
                    ])

def reload_module_allocation_settings():
    """Insert the stored module allocation settings back into the UI
    """
    if module_data.is_set():
        if required_credits_per_student_data.is_set():
            ui.update_numeric(f"required_credits_per_student", value=required_credits_per_student_data.get())

        if module_groups_data_maxs.is_set():
            for i, _ in enumerate(module_groups_data()):
                ui.update_numeric(f"max_credits_module_group_{i}", value=module_groups_data_maxs.get()[i])

        if module_groups_data_mins.is_set():
            for i, _ in enumerate(module_groups_data()):
                ui.update_numeric(f"min_credits_module_group_{i}", value=module_groups_data_mins.get()[i])

        if semesters_data_maxs.is_set():
            for i, _ in enumerate(semesters_data()):
                ui.update_numeric(f"max_credits_semester_{i}", value=semesters_data_maxs.get()[i])

        if semesters_data_mins.is_set():
            for i, _ in enumerate(semesters_data()):
                ui.update_numeric(f"min_credits_semester_{i}", value=semesters_data_mins.get()[i])
        


def run_assignments(
    repetition: int,
    previous_assignment: ModuleAssigner,
    halt_after_n_assignments: int,
    check_constraints: bool,
    loaded_module_assignments: pd.DataFrame,
):
    print(f"Running {repetition}")
    successful_assignments = []
    successful_assignment_mean_scores = []
    successful_assignment_median_scores = []

    module_assigner = ModuleAssigner(
        student_data.get(),
        module_data.get(),
        input.required_credits_per_student.get(),
        dict(
            zip(
                module_groups_data.get(),
                [
                    input[f"max_credits_module_group_{i}"].get()
                    for i, _ in enumerate(module_groups_data())
                ],
            )
        ),
        dict(
            zip(
                semesters_data.get(),
                [
                    input[f"max_credits_semester_{i}"].get()
                    for i, _ in enumerate(semesters_data())
                ],
            )
        ),
        dict(
            zip(
                module_groups_data.get(),
                [
                    input[f"min_credits_module_group_{i}"].get()
                    for i, _ in enumerate(module_groups_data())
                ],
            )
        ),
        dict(
            zip(
                semesters_data.get(),
                [
                    input[f"min_credits_semester_{i}"].get()
                    for i, _ in enumerate(semesters_data())
                ],
            )
        ),
        input["custom_random_seed"].get() + repetition * input["custom_random_seed"].get() + 1,
    )

    print(f"Module assigner seed: {module_assigner._random_seed}")

    print("Loading pre-existing module assignments")
    if not loaded_module_assignments is None:
        module_assigner.set_loaded_module_assignments(loaded_module_assignments)

    result_messages = []
    for i in range(halt_after_n_assignments):
        result_messages = module_assigner.run_assignment_round()


    semester_min_credits_satisfied, semester_labels = module_assigner.assignment_satisfies_minimum_credits_per_semester()
    semester_minimum_satisfied = np.all(semester_min_credits_satisfied)

    group_min_credits_satisfield, group_labels = module_assigner.assignment_satisfies_minimum_credits_per_group()
    group_minimum_satisfied = np.all(group_min_credits_satisfield)

    total_credits_satisfied = module_assigner.get_assigned_credits_totals() == module_assigner._required_credits_per_student
    credit_total_satisfied = np.all(total_credits_satisfied)

    print(f"semester_minimum_satisfied = {semester_minimum_satisfied} | group_minimum_satisfied = {group_minimum_satisfied} | credit_total_satisfied = {credit_total_satisfied}")
 
    if (
        semester_minimum_satisfied
        and group_minimum_satisfied
        and credit_total_satisfied
    ) or (not check_constraints):
        successful_assignments.append(module_assigner)

    best_assignment = previous_assignment
    if len(successful_assignments) > 0:
        if best_assignment is None:
            best_assignment = successful_assignments[0]
        else:
            previous_scores = best_assignment.get_assignment_satisfaction_scores()
            current_scores = successful_assignments[
                0
            ].get_assignment_satisfaction_scores()

            previous_overallocation = best_assignment.get_excess_module_requests()
            current_overallocation = successful_assignments[
                0
            ].get_excess_module_requests()

            previous_overallocation_mean = previous_overallocation["proportion_overrequested"].mean()
            current_overallocation_mean = current_overallocation["proportion_overrequested"].mean()

            previous_mean_score = np.nanmean(previous_scores)
            current_mean_score = np.nanmean(current_scores)

            best_assignment = (
                successful_assignments[0]
                if (current_mean_score >= previous_mean_score)
                else best_assignment
            )
            if (current_mean_score >= previous_mean_score) and (current_overallocation_mean <= previous_overallocation_mean):
                best_assignment = successful_assignments[0]
                print(f"Updated best assignment {repetition} {previous_mean_score} {current_mean_score}")
            
    return best_assignment
