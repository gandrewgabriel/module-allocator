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

MAX_SIZE = 50000
ACCEPTED_FILETYPES = [".csv"]

module_data = reactive.value()
module_data_error = reactive.value()
_ = module_data_error.set(False)
module_groups_data = reactive.value()
semesters_data = reactive.value()

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


@render.express
def _():
    with ui.navset_pill(id="tab"):

        @render.express
        def _():
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
                                    "allow_lowest_preferences",
                                    "Allow allocation of lowest preferences",
                                    False,
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
        students, students_missing_ranks, students_missing_ids, missing_modules = (
            load_students(
                student_module_rankings.get(),
                student_group_preferences.get(),
                module_data.get(),
            )
        )
        student_data.set(students)
        print(student_data.get())
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
    student_group_preferences.set(None)
    student_group_preferences.unset()
    student_data.unset()


@reactive.effect
@reactive.event(input.reset_module_rankings_data)
def _():
    student_module_rankings.set(None)
    student_module_rankings.unset()
    student_data.unset()


@reactive.effect
@reactive.event(input.reset_prior_allocations_data)
def _():
    student_previous_module_allocations.set(None)
    student_previous_module_allocations.unset()


@reactive.effect
@reactive.event(input.modules_file)
def file_content():
    modules_file_info = input.modules_file()[0]
    if not modules_file_info:
        return

    try:
        module_dataframe = load_module_data(Path(modules_file_info["datapath"]))
        errors = validate_module_data(module_dataframe)

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
        ) = get_formatted_module_data(module_dataframe)
        module_data.set(modules)
        module_groups_data.set(module_groups)
        semesters_data.set(semesters)
        module_data_error.set(False)
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
        student_previous_module_allocations.set(student_previous_assignments_data)
        student_previous_module_allocations_error.set(False)
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
                    False,
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
        repetition * 123,
    )

    print("Loading pre-existing module assignments")
    if not loaded_module_assignments is None:
        module_assigner.set_loaded_module_assignments(loaded_module_assignments)

    result_messages = []
    for i in range(halt_after_n_assignments):
        result_messages = module_assigner.run_assignment_round(
            input["allow_lowest_preferences"].get()
        )

    semester_minimum_satisfied = np.all(
        module_assigner.assignment_satisfies_minimum_credits_per_semester()
    )
    group_minimum_satisfied = np.all(
        module_assigner.assignment_satisfies_minimum_credits_per_group()
    )
    credit_total_satisfied = np.all(
        module_assigner.get_assigned_credits_totals()
        == module_assigner._required_credits_per_student
    )

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

            previous_mean_score = np.mean(previous_scores)
            current_mean_score = np.mean(current_scores)
            previous_min_score = np.min(previous_scores)
            current_min_score = np.min(current_scores)

            best_assignment = (
                successful_assignments[0]
                if (current_mean_score >= previous_mean_score)
                and (current_min_score >= previous_min_score)
                else best_assignment
            )
            if (current_mean_score >= previous_mean_score) and (
                current_min_score >= previous_min_score
            ):
                print(
                    f"Updated best assignment {repetition} {previous_mean_score} {current_mean_score}"
                )

    return best_assignment
