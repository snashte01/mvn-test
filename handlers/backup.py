from templates.backup import render_backup_page


def run_trigger(params):
    return render_backup_page(
        message='Backup console is coming in Phase 2.',
        msg_type='info',
    )
