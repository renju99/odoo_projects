from odoo import models, fields, api, _
from datetime import datetime
import io, base64
import matplotlib.pyplot as plt
from collections import Counter
import calendar

class MonthlyBuildingReportWizard(models.TransientModel):
    _name = 'monthly.building.report.wizard'
    _description = 'Monthly Building Maintenance Report Wizard'

    building_id = fields.Many2one('facilities.building', string='Building', required=True)
    year = fields.Integer('Year', required=True, default=lambda self: datetime.now().year)
    month = fields.Selection(
        [(str(i), calendar.month_name[i]) for i in range(1, 13)],
        string='Month', required=True, default=lambda self: str(datetime.now().month))

    def action_generate_pdf_report(self):
        year, month = int(self.year), int(self.month)
        start_dt = datetime(year, month, 1)
        end_dt = datetime(year + (month == 12), (month % 12) + 1, 1)
        workorders = self.env['maintenance.workorder'].search([
            ('building_id', '=', self.building_id.id),
            ('create_date', '>=', start_dt),
            ('create_date', '<', end_dt),
        ])

        # Mappings for friendly names
        STATUS_LABELS = {
            'in_progress': 'In Progress',
            'done': 'Completed',
            'draft': 'Draft',
            'cancel': 'Cancelled',
            'new': 'New',
        }
        PRIORITY_LABELS = {
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low',
        }
        TYPE_LABELS = {
            'corrective': 'Corrective',
            'preventive': 'Preventive',
            'inspection': 'Inspection',
        }
        SLA_LABELS = {
            'compliant': 'Compliant',
            'breached': 'Breached',
            'not_applicable': 'Not Applicable',
        }

        # Map technical to friendly names for counts
        status_counts = Counter(w.status for w in workorders)
        status_counts_friendly = Counter()
        for k, v in status_counts.items():
            status_counts_friendly[STATUS_LABELS.get(k, k)] = v

        type_counts = Counter(w.work_order_type for w in workorders)
        type_counts_friendly = Counter()
        for k, v in type_counts.items():
            type_counts_friendly[TYPE_LABELS.get(k, k)] = v

        priority_counts = Counter(w.priority for w in workorders)
        priority_counts_friendly = Counter()
        for k, v in priority_counts.items():
            priority_counts_friendly[PRIORITY_LABELS.get(k, k)] = v

        asset_counts = Counter(w.asset_id.name for w in workorders if w.asset_id)
        room_counts = Counter(w.room_id.name for w in workorders if w.room_id)
        parts_counts = Counter()
        for wo in workorders:
            for part in getattr(wo, 'parts_used_ids', []):
                parts_counts[getattr(part, 'product_id', None) and part.product_id.name or ''] += getattr(part, 'quantity', 0)
        completion_times = [
            (wo.actual_end_date - wo.actual_start_date).total_seconds()/3600
            for wo in workorders
            if wo.status == 'done' and wo.actual_start_date and wo.actual_end_date
        ]
        avg_completion_time = round(sum(completion_times) / len(completion_times), 2) if completion_times else 0
        sla_status_counts = Counter(getattr(w, 'sla_resolution_status', None) for w in workorders)
        sla_status_counts_friendly = Counter()
        for k, v in sla_status_counts.items():
            sla_status_counts_friendly[SLA_LABELS.get(k, k)] = v

        desc_words = []
        for wo in workorders:
            if getattr(wo, 'description', None):
                desc_words += [w.lower() for w in wo.description.split() if len(w) > 4]
        issue_counts = Counter(desc_words)
        day_counts = Counter()
        for wo in workorders:
            if getattr(wo, 'create_date', None):
                day = wo.create_date.day
                day_counts[day] += 1
        top_assets = asset_counts.most_common(5)
        top_rooms = room_counts.most_common(5)
        top_parts = parts_counts.most_common(5)
        top_issues = issue_counts.most_common(5)

        def fig2base64(fig):
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode('utf-8')

        # Chart 1: Status Distribution (Pie)
        fig1, ax1 = plt.subplots()
        if status_counts_friendly:
            ax1.pie(list(status_counts_friendly.values()), labels=list(status_counts_friendly.keys()), autopct='%1.1f%%')
        ax1.set_title("Work Order Status Distribution")
        chart_status = fig2base64(fig1)

        # Chart 2: Work Orders by Type (Bar)
        fig2, ax2 = plt.subplots()
        if type_counts_friendly:
            ax2.bar(type_counts_friendly.keys(), type_counts_friendly.values(), color='skyblue')
        ax2.set_title("Work Orders by Type")
        chart_type = fig2base64(fig2)

        # Chart 3: Work Orders by Priority (Bar)
        fig3, ax3 = plt.subplots()
        if priority_counts_friendly:
            ax3.bar(priority_counts_friendly.keys(), priority_counts_friendly.values(), color='lightgreen')
        ax3.set_title("Work Orders by Priority")
        chart_priority = fig2base64(fig3)

        # Chart 4: Top Assets (Barh)
        fig4, ax4 = plt.subplots()
        if top_assets:
            ax4.barh([a[0] for a in top_assets], [a[1] for a in top_assets], color='orange')
        ax4.set_title("Top 5 Assets with Most Work Orders")
        chart_assets = fig2base64(fig4)

        # Chart 5: Top Rooms (Barh)
        fig5, ax5 = plt.subplots()
        if top_rooms:
            ax5.barh([r[0] for r in top_rooms], [r[1] for r in top_rooms], color='purple')
        ax5.set_title("Top 5 Rooms with Most Work Orders")
        chart_rooms = fig2base64(fig5)

        # Chart 6: Top Parts (Barh)
        fig6, ax6 = plt.subplots()
        if top_parts:
            ax6.barh([p[0] for p in top_parts], [p[1] for p in top_parts], color='teal')
        ax6.set_title("Top 5 Parts Used")
        chart_parts = fig2base64(fig6)

        # Chart 7: Work Orders by Day (Line)
        fig7, ax7 = plt.subplots()
        days_sorted = sorted(day_counts.keys())
        if days_sorted:
            ax7.plot(days_sorted, [day_counts[d] for d in days_sorted], marker='o')
        ax7.set_title("Work Orders by Day")
        ax7.set_xlabel("Day of Month")
        ax7.set_ylabel("Work Orders")
        chart_days = fig2base64(fig7)

        # Chart 8: SLA Compliance (Pie)
        fig8, ax8 = plt.subplots()
        if sla_status_counts_friendly:
            ax8.pie(list(sla_status_counts_friendly.values()), labels=list(sla_status_counts_friendly.keys()), autopct='%1.1f%%')
        ax8.set_title("SLA Compliance")
        chart_sla = fig2base64(fig8)

        # Chart 9: Wordcloud
        try:
            from wordcloud import WordCloud
            if desc_words:
                wc = WordCloud(width=400, height=200, background_color='white').generate(' '.join(desc_words))
                fig9 = plt.figure(figsize=(6,3))
                plt.imshow(wc, interpolation='bilinear')
                plt.axis('off')
                chart_wordcloud = fig2base64(fig9)
            else:
                chart_wordcloud = None
        except ImportError:
            chart_wordcloud = None

        # Pass all data to QWeb
        data = {
            'building': self.building_id.name,
            'year': self.year,
            'month': calendar.month_name[int(self.month)],
            'total': len(workorders),
            'status_counts': status_counts_friendly,
            'type_counts': type_counts_friendly,
            'priority_counts': priority_counts_friendly,
            'top_assets': top_assets,
            'top_rooms': top_rooms,
            'top_parts': top_parts,
            'top_issues': top_issues,
            'avg_completion_time': avg_completion_time,
            'sla_status_counts': sla_status_counts_friendly,
            'chart_status': chart_status,
            'chart_type': chart_type,
            'chart_priority': chart_priority,
            'chart_assets': chart_assets,
            'chart_rooms': chart_rooms,
            'chart_parts': chart_parts,
            'chart_days': chart_days,
            'chart_sla': chart_sla,
            'chart_wordcloud': chart_wordcloud,
            'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        return self.env.ref('facilities_management.monthly_building_report_pdf_action').report_action(self, data={'doc': data})