"""View package: every module re-exported so `from . import views` keeps working."""

from .academics import (  # noqa: F401
                       attendance_entry,
                       exam_schedule_create,
                       exam_schedule_delete,
                       exam_schedule_edit,
                       exam_schedule_list,
                       marks_entry,
                       results_view,
                       subject_create,
                       subject_delete,
                       subject_edit,
                       subject_list,
                       take_attendance_bulk,
)
from .common import (
                       admin_required,
                       healthz,
                       help_center,
                       is_admin,
                       is_teacher,
                       manifest,
                       offline,
                       privacy_policy,  # noqa: F401
                       readyz,
                       service_worker,
                       teacher_required,
                       terms_of_use,
)
from .content import (  # noqa: F401
                       ai_chatbot_api,
                       banner_delete,
                       banner_upload,
                       doubt_delete,
                       doubt_detail,
                       doubt_edit,
                       doubt_list,
                       event_create,
                       event_delete,
                       event_edit,
                       event_list,
                       notice_create,
                       notice_delete,
                       notice_edit,
                       notice_list,
                       reply_delete,
                       reply_edit,
)
from .dashboard import (  # noqa: F401
                       admin_dashboard,
                       reports_view,
                       teacher_dashboard,
)
from .finance import (  # noqa: F401
                       fee_payment_create,
                       fee_payments,
                       fee_structure_create,
                       fee_structure_delete,
                       fee_structure_edit,
                       fee_structure_list,
)
from .imports import (  # noqa: F401
                       csv_upload,
                       upload_history,
)
from .landing import landing_page  # noqa: F401
from .leave_feedback import (  # noqa: F401
                       feedback_report,
                       leave_applications,
                       leave_review,
)
from .media import serve_media  # noqa: F401
from .people import (  # noqa: F401
                       admin_create,
                       admin_delete,
                       admin_edit,
                       admin_list,
                       export_set_password_links_csv,
                       export_students_csv,
                       student_anonymize,
                       student_create,
                       student_data_export,
                       student_delete,
                       student_edit,
                       student_list,
                       teacher_create,
                       teacher_delete,
                       teacher_edit,
                       teacher_list,
)
from .reports_feedback import (  # noqa: F401
                       bug_report_list,
                       bug_report_update,
                       report_problem,
)
from .teacher import (  # noqa: F401
                       teacher_assignments,
                       teacher_marks,
                       teacher_materials,
                       teacher_notice_delete,
                       teacher_notice_edit,
                       teacher_notices,
                       teacher_schedule,
                       teacher_students,
                       teacher_take_attendance,
)
