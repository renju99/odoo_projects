# models/predictive_maintenance.py
from odoo import models, fields

class PredictiveMaintenance(models.Model):
    _name = 'predictive.maintenance'
    _inherit = 'asset.maintenance.schedule'

    algorithm = fields.Selection([
        ('linear', 'Linear Regression'),
        ('mlp', 'Neural Network'),
        ('svm', 'SVM')
    ], default='linear')
    training_data = fields.Binary('Dataset')
    accuracy = fields.Float(compute='_compute_accuracy')