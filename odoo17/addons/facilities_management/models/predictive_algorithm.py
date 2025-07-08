# models/predictive_algorithm.py
from odoo import models, fields


class PredictiveAlgorithm(models.Model):
    _name = 'predictive.algorithm'
    _description = 'Predictive Maintenance Algorithms'

    name = fields.Char(required=True, string="Algorithm Name")
    model_type = fields.Selection(
        selection=[
            ('linear', 'Linear Regression'),
            ('random_forest', 'Random Forest'),
            ('neural_net', 'Neural Network'),
            ('svm', 'Support Vector Machine')
        ],
        string="Model Type",
        required=True
    )
    asset_type_ids = fields.Many2many(
        comodel_name='ir.model',
        relation='algorithm_asset_type_rel',
        column1='algorithm_id',
        column2='model_id',
        string="Applicable Asset Types",
        domain=[('model', '=like', 'facilities.%')]
    )
    active = fields.Boolean(default=True)
    code_implementation = fields.Text(
        string="Custom Code",
        help="Paste Python implementation for custom algorithms"
    )