# /home/ranjith/odoo_projects/odoo17/addons/facilities_management/models/maintenance_workorder.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class MaintenanceWorkOrder(models.Model):
    _name = 'maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Work Order Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Maintenance Schedule')
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Type', default='corrective', required=True)
    technician_id = fields.Many2one('hr.employee', string='Primary Technician', domain="[('is_technician', '=', True)]")
    start_date = fields.Datetime(string='Scheduled Start Date')
    end_date = fields.Datetime(string='Scheduled End Date')
    actual_start_date = fields.Datetime(string='Actual Start Date', readonly=True)
    actual_end_date = fields.Datetime(string='Actual End Date', readonly=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)
    assignment_ids = fields.One2many('maintenance.workorder.assignment', 'workorder_id', string='Assignments')
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
    ], string='Priority', default='1')

    description = fields.Text(string='Work Order Description')
    work_done = fields.Text(string='Work Done Notes')
    parts_used_ids = fields.One2many('maintenance.workorder.part_line', 'workorder_id', string='Parts Used')

    picking_id = fields.Many2one('stock.picking', string='Parts Transfer', copy=False,
                                 help="The internal transfer for parts issued for this work order.")
    picking_count = fields.Integer(compute='_compute_picking_count', string='Transfers')
    has_parts = fields.Boolean(compute='_compute_has_parts', store=True, help="Indicates if this work order has parts lines.")

    # NEW FIELD: Link to the Job Plan (from schedule or manual selection)
    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan',
                                  help="The job plan linked to this work order, providing detailed tasks.")
    # NEW FIELD: Work Order specific tasks (copied from job plan or manually added)
    workorder_task_ids = fields.One2many('maintenance.workorder.task', 'workorder_id', string='Tasks', copy=True)
    all_tasks_completed = fields.Boolean(compute='_compute_all_tasks_completed', store=False,
                                         help="Indicates if all checklist tasks are marked as completed.")

    @api.depends('workorder_task_ids.is_done')
    def _compute_all_tasks_completed(self):
        for wo in self:
            if not wo.workorder_task_ids:
                wo.all_tasks_completed = True # No tasks means all are "completed"
            else:
                wo.all_tasks_completed = all(task.is_done for task in wo.workorder_task_ids if task.is_checklist_item)


    @api.depends('parts_used_ids')
    def _compute_has_parts(self):
        for rec in self:
            rec.has_parts = bool(rec.parts_used_ids)

    @api.depends('picking_id')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = 1 if rec.picking_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or _('New')
        records = super().create(vals_list)
        for rec in records:
            # After creation, if a job_plan_id is set, copy its tasks
            if rec.job_plan_id:
                _logger.info(f"WO {rec.name} (ID: {rec.id}) created with Job Plan {rec.job_plan_id.name}. Copying tasks.")
                rec._copy_job_plan_tasks()
        return records

    def write(self, vals):
        # Store original status before write
        old_status = {rec.id: rec.status for rec in self}
        res = super().write(vals)

        for rec in self:
            # Handle status change to 'in_progress'
            if 'status' in vals and vals['status'] == 'in_progress' and old_status[rec.id] != 'in_progress':
                if rec.has_parts and not rec.picking_id:
                    _logger.info(f"WO {rec.name} (ID: {rec.id}) status changed to 'in_progress'. Creating parts picking.")
                    rec._create_or_update_parts_picking()

            # Handle parts_used_ids change OR (status change to in_progress AND has_parts)
            if 'parts_used_ids' in vals and rec.status == 'in_progress':
                 _logger.info(f"WO {rec.name}: parts_used_ids changed while 'in_progress'. Updating parts picking.")
                 rec._create_or_update_parts_picking()

            # Handle status change to 'cancelled'
            if 'status' in vals and vals['status'] == 'cancelled' and old_status[rec.id] != 'cancelled':
                _logger.info(f"WO {rec.name}: status changed to 'cancelled'. Calling _handle_parts_on_cancel.")
                rec._handle_parts_on_cancel()
        return res

    def _get_stock_locations(self):
        """ Helper to get the default source and destination stock locations for parts transfer. """
        source_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if not source_location:
            source_location = self.env['stock.location'].search([('usage', '=', 'internal'), ('active', '=', True), ('name', 'ilike', 'stock')], limit=1)
            if not source_location:
                raise UserError(_("Default source stock location 'WH/Stock' not found by external ID or by searching internal locations. Please ensure it exists or configure a different one."))

        destination_location = self.env.ref('stock.stock_location_products_virtual_location', raise_if_not_found=False)
        if not destination_location:
            destination_location = self.env['stock.location'].search([('usage', '=', 'production'), ('active', '=', True)], limit=1)
            if not destination_location:
                destination_location = self.env['stock.location'].search([('usage', '=', 'inventory'), ('active', '=', True)], limit=1)
            if not destination_location:
                destination_location = self.env.ref('stock.stock_location_scrap', raise_if_not_found=False)

        if not destination_location:
            raise UserError(_("Could not find a suitable default consumption stock location. Please ensure 'Virtual Locations/Consumption' (or similar with usage 'Production' or 'Inventory') exists and is active, or manually configure a different destination."))

        return source_location, destination_location

    def _create_or_update_parts_picking(self):
        """ Creates or updates the internal stock picking for parts needed in the work order. """
        self.ensure_one()
        source_location, destination_location = self._get_stock_locations()
        Picking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        picking_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not picking_type:
            raise UserError(_("Internal Transfer picking type 'stock.picking_type_internal' not found. Please ensure it exists."))

        if not self.has_parts:
            if self.picking_id:
                if self.picking_id.state in ('draft', 'waiting', 'confirmed', 'assigned'):
                    _logger.info(f"WO {self.name}: No parts, cancelling picking {self.picking_id.name}.")
                    self.picking_id.action_cancel()
                    self.message_post(body=_("Associated parts transfer %s has been cancelled because all parts were removed.") % self.picking_id.name)
                elif self.picking_id.state == 'done':
                    _logger.warning(f"WO {self.name}: No parts, but picking {self.picking_id.name} is 'done'. Cannot cancel, leaving linked.")
                    self.message_post(body=_("Associated parts transfer %s is already completed and cannot be unlinked or cancelled by removing all parts.") % self.picking_id.name)
            self.picking_id = False
            return

        if not self.picking_id:
            _logger.info(f"WO {self.name}: Creating new parts picking.")
            self.picking_id = Picking.create({
                'picking_type_id': picking_type.id,
                'location_id': source_location.id,
                'location_dest_id': destination_location.id,
                'origin': self.name,
                'note': f"Parts transfer for Maintenance Work Order: {self.name}",
                'workorder_id': self.id,
            })
            _logger.info(f"WO {self.name}: New picking created: {self.picking_id.name} (ID: {self.picking_id.id})")

        if self.picking_id.state not in ('draft', 'waiting', 'confirmed', 'assigned'):
            raise UserError(_("Cannot modify parts transfer: The transfer %s is already processed (%s). Please create a new work order or handle parts manually.") % (self.picking_id.name, self.picking_id.state))

        current_part_lines_map = {line.product_id.id: line for line in self.parts_used_ids}
        existing_moves = self.picking_id.move_ids_without_package
        moves_to_unlink = self.env['stock.move']

        for move in existing_moves:
            if move.product_id.id in current_part_lines_map:
                part_line = current_part_lines_map[move.product_id.id]
                if (abs(move.product_uom_qty - part_line.quantity) > 0.001 or
                    move.product_uom.id != part_line.uom_id.id):
                    _logger.debug(f"WO {self.name}: Updating move {move.name} qty from {move.product_uom_qty} to {part_line.quantity}, UOM from {move.product_uom.name} to {part_line.uom_id.name}")
                    move.write({
                        'product_uom_qty': part_line.quantity,
                        'product_uom': part_line.uom_id.id,
                    })
                del current_part_lines_map[move.product_id.id]
            else:
                moves_to_unlink += move

        if moves_to_unlink:
            _logger.info(f"WO {self.name}: Unlinking {len(moves_to_unlink)} obsolete moves from picking {self.picking_id.name}.")
            moves_to_unlink.unlink()

        moves_to_create = []
        for product_id, part_line in current_part_lines_map.items():
            moves_to_create.append({
                'name': part_line.product_id.name,
                'product_id': part_line.product_id.id,
                'product_uom_qty': part_line.quantity,
                'product_uom': part_line.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': destination_location.id,
                'picking_id': self.picking_id.id,
                'workorder_id': self.id,
            })
        if moves_to_create:
            _logger.info(f"WO {self.name}: Creating {len(moves_to_create)} new moves for picking {self.picking_id.name}.")
            StockMove.create(moves_to_create)

        if self.picking_id.state == 'draft':
            _logger.info(f"WO {self.name}: Confirming picking {self.picking_id.name}.")
            self.picking_id.action_confirm()

    def _handle_parts_on_cancel(self):
        """ Handles associated parts picking when the work order is cancelled. """
        self.ensure_one()
        _logger.info(f"Entering _handle_parts_on_cancel for WO {self.name} (ID: {self.id}). Picking ID: {self.picking_id.id if self.picking_id else 'None'}, State: {self.picking_id.state if self.picking_id else 'None'}")

        if not self.picking_id:
            _logger.info(f"WO {self.name}: No picking to handle on cancellation.")
            return

        if self.picking_id.state in ('draft', 'waiting', 'confirmed', 'assigned'):
            _logger.info(f"WO {self.name}: Picking {self.picking_id.name} is in state '{self.picking_id.state}'. Attempting to cancel.")
            try:
                self.picking_id.action_cancel()
                self.message_post(body=_("Associated parts transfer %s has been cancelled due to work order cancellation.") % self.picking_id.name)
                _logger.info(f"WO {self.name}: Picking {self.picking_id.name} successfully cancelled.")
            except Exception as e:
                _logger.error(f"WO {self.name}: Failed to cancel picking {self.picking_id.name}: {e}")
                self.message_post(body=_("Warning: Could not automatically cancel associated parts transfer %s. Please cancel it manually. Error: %s") % (self.picking_id.name, str(e)))
        elif self.picking_id.state == 'done':
            _logger.info(f"WO {self.name}: Picking {self.picking_id.name} is 'done'. Creating a return transfer.")
            source_location, destination_location = self._get_stock_locations()

            picking_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
            if not picking_type:
                raise UserError(_("Internal Transfer picking type 'stock.picking_type_internal' not found."))

            return_picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': destination_location.id,
                'location_dest_id': source_location.id,
                'origin': f"Return for {self.picking_id.name} ({self.name})",
                'note': f"Parts return for cancelled Maintenance Work Order: {self.name}",
                'workorder_id': self.id,
            }
            return_picking = self.env['stock.picking'].create(return_picking_vals)
            _logger.info(f"WO {self.name}: Return picking {return_picking.name} created for picking {self.picking_id.name}.")

            for move in self.picking_id.move_ids_without_package:
                qty_to_return = move.quantity_done
                if qty_to_return > 0:
                    _logger.debug(f"WO {self.name}: Creating return move for {move.product_id.name}, Qty: {qty_to_return}.")
                    self.env['stock.move'].create({
                        'name': f"Return: {move.product_id.name}",
                        'product_id': move.product_id.id,
                        'product_uom_qty': qty_to_return,
                        'product_uom': move.product_uom.id,
                        'location_id': destination_location.id,
                        'location_dest_id': source_location.id,
                        'picking_id': return_picking.id,
                        'workorder_id': self.id,
                        'state': 'draft',
                    })

            if return_picking.move_ids_without_package:
                return_picking.action_confirm()
                self.message_post(body=_("A return transfer %s has been created for parts due to work order cancellation. It needs to be validated.") % return_picking.name)
                _logger.info(f"WO {self.name}: Return picking {return_picking.name} confirmed.")
            else:
                 _logger.info(f"WO {self.name}: No moves created for return picking {return_picking.name}, unlinking it.")
                 return_picking.unlink()
                 self.message_post(body=_("Work order cancelled, but no parts were issued to return."))
        elif self.picking_id.state == 'cancel':
            _logger.info(f"WO {self.name}: Picking {self.picking_id.name} is already cancelled. No action needed.")
            self.message_post(body=_("Associated parts transfer %s was already cancelled.") % self.picking_id.name)
        else:
            _logger.warning(f"WO {self.name}: Picking {self.picking_id.name} is in unexpected state '{self.picking_id.state}' during cancellation. Manual intervention may be needed.")
            self.message_post(body=_("Warning: Associated parts transfer %s is in an unexpected state (%s) and could not be handled automatically.") % (self.picking_id.name, self.picking_id.state))

    def action_start_progress(self):
        """Moves work order to 'In Progress' state and sets actual start date."""
        for rec in self:
            if rec.status == 'draft':
                rec.write({
                    'status': 'in_progress',
                    'actual_start_date': fields.Datetime.now(),
                })
            else:
                raise UserError(_("Work order must be in 'Draft' state to start progress."))

    def action_complete(self):
        """Moves work order to 'Completed' state and sets actual end date.
           Also validates the associated parts picking if it exists and is not done.
           Requires all checklist tasks to be completed."""
        for rec in self:
            if rec.status == 'in_progress':
                if not rec.all_tasks_completed:
                    raise UserError(_("Cannot complete work order: Not all checklist tasks are marked as completed."))

                if rec.picking_id and rec.picking_id.state not in ('done', 'cancel'):
                    _logger.info(f"WO {rec.name}: Attempting to validate picking {rec.picking_id.name} before completion.")
                    try:
                        rec.picking_id.button_validate()
                        rec.message_post(body=_("Associated parts transfer %s has been completed.") % rec.picking_id.name)
                        _logger.info(f"WO {rec.name}: Picking {rec.picking_id.name} successfully validated.")
                    except UserError as e:
                        _logger.error(f"WO {rec.name}: Failed to validate picking {rec.picking_id.name}: {e}")
                        raise UserError(_("Could not complete work order: %s. Please validate parts transfer manually if there are stock issues.") % e.name)
                    except Exception as e:
                        _logger.error(f"WO {rec.name}: Unexpected error validating picking {rec.picking_id.name}: {e}")
                        raise UserError(_("An unexpected error occurred while validating parts transfer %s. Please check server logs and validate manually if necessary.") % rec.picking_id.name)
                elif rec.picking_id and rec.picking_id.state == 'cancel':
                    raise UserError(_("Cannot complete work order: Associated parts transfer %s is cancelled. Please reset parts or create a new transfer.") % rec.picking_id.name)
                elif rec.picking_id and rec.picking_id.state == 'done':
                    _logger.info(f"WO {rec.name}: Picking {rec.picking_id.name} is already done.")

                rec.write({
                    'status': 'done',
                    'actual_end_date': fields.Datetime.now(),
                })
                if rec.schedule_id and rec.actual_end_date:
                    rec.schedule_id.last_maintenance_date = rec.actual_end_date.date()
            else:
                raise UserError(_("Work order must be 'In Progress' to complete."))

    def action_cancel(self):
        """Moves work order to 'Cancelled' state. Triggers parts handling."""
        for rec in self:
            if rec.status not in ('done', 'cancelled'):
                rec.write({'status': 'cancelled'})
            else:
                raise UserError(_("Cannot cancel a completed or already cancelled work order."))

    def action_reset_to_draft(self):
        """Resets a completed or cancelled work order back to 'Draft'."""
        for rec in self:
            if rec.status in ('done', 'cancelled'):
                if rec.picking_id and rec.picking_id.state == 'done':
                    raise UserError(_("Cannot reset to draft: Parts were already issued via transfer %s. Please manage the parts return manually if needed, then cancel the work order.") % rec.picking_id.name)
                elif rec.picking_id and rec.picking_id.state not in ('cancel', 'draft'):
                    _logger.info(f"WO {rec.name}: Resetting to draft. Cancelling pending picking {rec.picking_id.name}.")
                    rec.picking_id.action_cancel()
                    rec.message_post(body=_("Associated parts transfer %s has been cancelled due to reset.") % rec.picking_id.name)
                elif rec.picking_id and rec.picking_id.state == 'cancel':
                    _logger.info(f"WO {rec.name}: Picking {rec.picking_id.name} already cancelled. Detaching link.")
                    rec.picking_id = False

                rec.write({
                    'status': 'draft',
                    'actual_start_date': False,
                    'actual_end_date': False,
                })
            else:
                raise UserError(_("Only completed or cancelled work orders can be reset to draft."))

    def action_view_picking(self):
        """Action to open the associated stock picking via smart button."""
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No parts transfer associated with this work order."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Parts Transfer'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref('stock.view_picking_form').id, 'form')],
            'target': 'current',
        }

    def action_validate_parts_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No parts transfer associated with this work order."))
        if self.picking_id.state in ('done', 'cancel'):
            raise UserError(_("Parts transfer is already %s and cannot be validated.") % self.picking_id.state)

        _logger.info(f"WO {self.name}: Manual validation of picking {self.picking_id.name}.")
        try:
            self.picking_id.button_validate()
            self.message_post(body=_("Parts transfer %s has been manually validated.") % self.picking_id.name)
            _logger.info(f"WO {self.name}: Picking {self.picking_id.name} successfully validated manually.")
        except UserError as e:
            _logger.error(f"WO {self.name}: Failed to validate parts transfer {self.picking_id.name} manually: {e}")
            raise UserError(_("Failed to validate parts transfer: %s. Please check stock availability and resolve issues.") % e.name)
        except Exception as e:
            _logger.error(f"WO {self.name}: Unexpected error during manual validation of picking {self.picking_id.name}: {e}")
            raise UserError(_("An unexpected error occurred during manual validation of parts transfer. Please check server logs."))

    def _copy_job_plan_tasks(self):
        """
        Copies tasks from the linked job plan to the work order's tasks.
        This method is called during work order creation if job_plan_id is set.
        """
        self.ensure_one()
        if self.job_plan_id and not self.workorder_task_ids: # Only copy if job plan exists and no tasks are already present
            tasks_to_create = []
            for task_template in self.job_plan_id.task_ids.sorted('sequence'):
                tasks_to_create.append({
                    'workorder_id': self.id,
                    'name': task_template.name,
                    'sequence': task_template.sequence,
                    'description': task_template.description,
                    'frequency_type': task_template.frequency_type,
                    'is_checklist_item': task_template.is_checklist_item,
                    'is_done': False, # New tasks are always not done
                    'notes': False, # No notes initially
                })
            if tasks_to_create:
                self.env['maintenance.workorder.task'].create(tasks_to_create)
                _logger.info(f"WO {self.name}: Copied {len(tasks_to_create)} tasks from Job Plan {self.job_plan_id.name}.")
            else:
                _logger.info(f"WO {self.name}: Job Plan {self.job_plan_id.name} has no tasks to copy.")

    @api.constrains('status', 'workorder_task_ids', 'all_tasks_completed')
    def _check_tasks_on_completion(self):
        for rec in self:
            if rec.status == 'done' and not rec.all_tasks_completed:
                # This constraint prevents saving 'done' if tasks are not complete.
                # The 'action_complete' button already has this check, but this adds a backend layer.
                raise ValidationError(_("Cannot mark Work Order as 'Completed' if not all checklist tasks are marked as done."))


class MaintenanceWorkOrderTask(models.Model):
    _name = 'maintenance.workorder.task'
    _description = 'Maintenance Work Order Task'
    _order = 'sequence, id'

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order', required=True, ondelete='cascade')
    name = fields.Char(string='Task Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Instructions')
    frequency_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Biannual'),
        ('annual', 'Annual'),
        ('ad_hoc', 'Ad-hoc / As Needed'),
        ('other', 'Other'),
    ], string='Recommended Frequency', default='ad_hoc')
    is_checklist_item = fields.Boolean(string='Checklist Item', default=True,
                                        help="If checked, this task appears as a checkbox and must be completed to finish the WO.")
    is_done = fields.Boolean(string='Completed', default=False, tracking=True)
    notes = fields.Text(string='Notes / Findings')

    # Add a constraint to ensure 'is_done' can only be changed when WO is in_progress
    @api.constrains('is_done')
    def _check_workorder_status_for_task_done(self):
        for rec in self:
            if rec.is_done and rec.workorder_id.status != 'in_progress':
                # Allow marking done if WO is already done, useful if edited after completion
                if rec.workorder_id.status not in ('done', 'cancelled'):
                    raise ValidationError(_("Tasks can only be marked as completed when the Work Order is 'In Progress'."))
            # You might also add a constraint to prevent changing `is_done` from True to False
            # if the WO is already done, or add group permissions.