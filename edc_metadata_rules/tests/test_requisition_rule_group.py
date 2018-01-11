from collections import OrderedDict
from django.test import TestCase, tag
from edc_base import get_utcnow
from edc_constants.constants import MALE, FEMALE
from edc_metadata import NOT_REQUIRED, REQUIRED, KEYED, InvalidTargetPanel
from edc_metadata.models import RequisitionMetadata
from edc_reference import site_reference_configs
from edc_reference.models import Reference
from edc_visit_schedule.site_visit_schedules import site_visit_schedules
from edc_visit_tracking.constants import SCHEDULED
from faker import Faker

from ..predicate import P
from ..requisition import RequisitionRuleGroupMetaOptionsError
from ..requisition import RequisitionRuleGroup, RequisitionRule
from ..site import site_metadata_rules
from .reference_configs import register_to_site_reference_configs
from .models import Appointment, SubjectVisit, SubjectConsent, SubjectRequisition
from .visit_schedule import visit_schedule
from .models import CrfOne
from edc_facility.import_holidays import import_holidays

fake = Faker()


class RequisitionPanel:
    def __init__(self, name):
        self.name = name


panel_one = RequisitionPanel('one')
panel_two = RequisitionPanel('two')
panel_three = RequisitionPanel('three')
panel_four = RequisitionPanel('four')
panel_five = RequisitionPanel('five')
panel_six = RequisitionPanel('six')
panel_seven = RequisitionPanel('seven')
panel_eight = RequisitionPanel('eight')


class BadPanelsRequisitionRuleGroup(RequisitionRuleGroup):
    """Specifies invalid panel names.
    """

    rule = RequisitionRule(
        predicate=P('gender', 'eq', MALE),
        consequence=REQUIRED,
        alternative=NOT_REQUIRED,
        target_panels=['blah1', 'blah2'])

    class Meta:
        app_label = 'edc_metadata_rules'
        source_model = 'edc_metadata_rules.crfone'
        requisition_model = 'subjectrequisition'


class RequisitionRuleGroup2(RequisitionRuleGroup):
    """A rule group where source model is a requisition.
    """

    male = RequisitionRule(
        predicate=P('gender', 'eq', MALE),
        consequence=REQUIRED,
        alternative=NOT_REQUIRED,
        source_panel=panel_five,
        target_panels=[panel_one, panel_two])

    female = RequisitionRule(
        predicate=P('gender', 'eq', FEMALE),
        consequence=REQUIRED,
        alternative=NOT_REQUIRED,
        source_panel=panel_six,
        target_panels=[panel_three, panel_four])

    class Meta:
        app_label = 'edc_metadata_rules'
        source_model = 'subjectrequisition'
        requisition_model = 'subjectrequisition'


class RequisitionRuleGroup3(RequisitionRuleGroup):
    """A rule group where source model is a requisition.
    """

    female = RequisitionRule(
        predicate=P('f1', 'eq', 'hello'),
        consequence=REQUIRED,
        alternative=NOT_REQUIRED,
        target_panels=[panel_six, panel_seven, panel_eight])

    class Meta:
        app_label = 'edc_metadata_rules'
        source_model = 'crfone'
        requisition_model = 'subjectrequisition'


class BaseRequisitionRuleGroup(RequisitionRuleGroup):

    male = RequisitionRule(
        predicate=P('gender', 'eq', MALE),
        consequence=REQUIRED,
        alternative=NOT_REQUIRED,
        target_panels=[panel_one, panel_two])

    female = RequisitionRule(
        predicate=P('gender', 'eq', FEMALE),
        consequence=REQUIRED,
        alternative=NOT_REQUIRED,
        target_panels=[panel_three, panel_four])

    class Meta:
        abstract = True


class MyRequisitionRuleGroup(BaseRequisitionRuleGroup):
    """A rule group where source model is NOT a requisition.
    """

    class Meta:
        app_label = 'edc_metadata_rules'
        source_model = 'crfone'
        requisition_model = 'subjectrequisition'


class TestRequisitionRuleGroup(TestCase):

    def setUp(self):

        import_holidays()
        register_to_site_reference_configs()
        site_visit_schedules._registry = {}
        site_visit_schedules.loaded = False
        site_visit_schedules.register(visit_schedule)
        site_reference_configs.register_from_visit_schedule(
            visit_models={
                'edc_appointment.appointment': 'edc_metadata_rules.subjectvisit'})
        _, self.schedule = site_visit_schedules.get_by_onschedule_model(
            'edc_metadata_rules.onschedule')
        site_metadata_rules.registry = OrderedDict()
        # site_metadata_rules.register(rule_group_cls=CrfRuleGroupGender)

    def enroll(self, gender=None):
        subject_identifier = fake.credit_card_number()
        subject_consent = SubjectConsent.objects.create(
            subject_identifier=subject_identifier,
            consent_datetime=get_utcnow(),
            gender=gender)
        self.schedule.put_on_schedule(
            subject_identifier=subject_identifier,
            onschedule_datetime=subject_consent.consent_datetime)
        self.appointment = Appointment.objects.get(
            subject_identifier=subject_identifier,
            visit_code=self.schedule.visits.first.code)
        subject_visit = SubjectVisit.objects.create(
            appointment=self.appointment, reason=SCHEDULED,
            subject_identifier=subject_identifier)
        return subject_visit

#     def test_rule_bad_panel_names(self):
#         subject_visit = self.enroll(gender=MALE)
#         self.assertRaises(
#             InvalidTargetPanel,
# BadPanelsRequisitionRuleGroup().evaluate_rules, visit=subject_visit)

    def test_rule_male(self):
        subject_visit = self.enroll(gender=MALE)
        rule_results, _ = MyRequisitionRuleGroup().evaluate_rules(visit=subject_visit)
        for panel_name in ['one', 'two']:
            with self.subTest(panel_name=panel_name):
                key = f'edc_metadata_rules.subjectrequisition'
                for rule_result in rule_results[
                        'MyRequisitionRuleGroup.male'][key]:
                    self.assertEqual(rule_result.entry_status, REQUIRED)
                for rule_result in rule_results[
                        'MyRequisitionRuleGroup.female'][key]:
                    self.assertEqual(rule_result.entry_status, NOT_REQUIRED)

    def test_rule_female(self):
        subject_visit = self.enroll(gender=FEMALE)
        rule_results, _ = MyRequisitionRuleGroup().evaluate_rules(visit=subject_visit)
        for panel_name in ['one', 'two']:
            with self.subTest(panel_name=panel_name):
                key = f'edc_metadata_rules.subjectrequisition'
                for rule_result in rule_results[
                        'MyRequisitionRuleGroup.female'].get(key):
                    self.assertEqual(rule_result.entry_status, REQUIRED)
                for rule_result in rule_results[
                        'MyRequisitionRuleGroup.male'].get(key):
                    self.assertEqual(rule_result.entry_status, NOT_REQUIRED)

    def test_source_panel_required_raises(self):
        try:
            class BadRequisitionRuleGroup(BaseRequisitionRuleGroup):

                class Meta:
                    app_label = 'edc_metadata_rules'
                    source_model = 'subjectrequisition'
                    requisition_model = 'subjectrequisition'
        except RequisitionRuleGroupMetaOptionsError:
            pass
        else:
            self.fail('RequisitionRuleGroupMetaOptionsError not raised')

    def test_source_panel_not_required_raises(self):
        try:
            class BadRequisitionRuleGroup(RequisitionRuleGroup):

                male = RequisitionRule(
                    predicate=P('gender', 'eq', MALE),
                    consequence=REQUIRED,
                    alternative=NOT_REQUIRED,
                    source_panel=panel_one,
                    target_panels=[panel_one, panel_two])

                female = RequisitionRule(
                    predicate=P('gender', 'eq', FEMALE),
                    consequence=REQUIRED,
                    alternative=NOT_REQUIRED,
                    source_panel=panel_two,
                    target_panels=[panel_three, panel_four])

                class Meta:
                    app_label = 'edc_metadata_rules'
                    source_model = 'crf_one'
                    requisition_model = 'subjectrequisition'
        except RequisitionRuleGroupMetaOptionsError:
            pass
        else:
            self.fail('RequisitionRuleGroupMetaOptionsError not raised')

    def test_rule_male_with_source_model_as_requisition(self):
        subject_visit = self.enroll(gender=MALE)
        rule_results, _ = RequisitionRuleGroup2().evaluate_rules(visit=subject_visit)
        for panel_name in ['one', 'two']:
            with self.subTest(panel_name=panel_name):
                key = f'edc_metadata_rules.subjectrequisition'
                for rule_result in rule_results[
                        'RequisitionRuleGroup2.male'][key]:
                    self.assertEqual(rule_result.entry_status, REQUIRED)
                for rule_result in rule_results[
                        'RequisitionRuleGroup2.female'][key]:
                    self.assertEqual(rule_result.entry_status, NOT_REQUIRED)

    def test_metadata_for_rule_male_with_source_model_as_requisition1(self):
        subject_visit = self.enroll(gender=MALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup2)
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_five.name)
        for panel_name in ['one', 'two']:
            with self.subTest(panel_name=panel_name):
                obj = RequisitionMetadata.objects.get(
                    model='edc_metadata_rules.subjectrequisition',
                    subject_identifier=subject_visit.subject_identifier,
                    visit_code=subject_visit.visit_code,
                    panel_name=panel_name)
                self.assertEqual(obj.entry_status, REQUIRED)

    def test_metadata_for_rule_male_with_source_model_as_requisition2(self):
        subject_visit = self.enroll(gender=MALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup2)
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_five.name)
        for panel_name in ['three', 'four']:
            with self.subTest(panel_name=panel_name):
                obj = RequisitionMetadata.objects.get(
                    model='edc_metadata_rules.subjectrequisition',
                    subject_identifier=subject_visit.subject_identifier,
                    visit_code=subject_visit.visit_code,
                    panel_name=panel_name)
                self.assertEqual(obj.entry_status, NOT_REQUIRED)

    def test_metadata_for_rule_female_with_source_model_as_requisition1(self):
        subject_visit = self.enroll(gender=FEMALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup2)
        Reference.objects.create(
            timepoint=subject_visit.visit_code,
            identifier=subject_visit.subject_identifier,
            report_datetime=subject_visit.report_datetime,
            field_name='panel_name',
            value_str=panel_five.name)
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_five.name)
        for panel_name in ['three', 'four']:
            with self.subTest(panel_name=panel_name):
                obj = RequisitionMetadata.objects.get(
                    model='edc_metadata_rules.subjectrequisition',
                    subject_identifier=subject_visit.subject_identifier,
                    visit_code=subject_visit.visit_code,
                    panel_name=panel_name)
                self.assertEqual(obj.entry_status, REQUIRED)

    def test_metadata_for_rule_female_with_source_model_as_requisition2(self):
        subject_visit = self.enroll(gender=FEMALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup2)
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_five.name)
        for panel_name in ['one', 'two']:
            with self.subTest(panel_name=panel_name):
                obj = RequisitionMetadata.objects.get(
                    model='edc_metadata_rules.subjectrequisition',
                    subject_identifier=subject_visit.subject_identifier,
                    visit_code=subject_visit.visit_code,
                    panel_name=panel_name)
                self.assertEqual(obj.entry_status, NOT_REQUIRED)

    def test_metadata_requisition(self):
        subject_visit = self.enroll(gender=FEMALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup3)
        CrfOne.objects.create(
            subject_visit=subject_visit, f1='hello')
        for panel_name in ['one', 'two', 'three', 'four', 'five']:
            with self.subTest(panel_name=panel_name):
                obj = RequisitionMetadata.objects.get(
                    model='edc_metadata_rules.subjectrequisition',
                    subject_identifier=subject_visit.subject_identifier,
                    visit_code=subject_visit.visit_code,
                    panel_name=panel_name)
                self.assertEqual(obj.entry_status, NOT_REQUIRED)

    @tag('1')
    def test_keyed_instance_ignores_rules(self):
        """Asserts if instance exists, rule is ignored.
        """
        subject_visit = self.enroll(gender=FEMALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup3)
        Reference.objects.create(
            timepoint=subject_visit.visit_code,
            identifier=subject_visit.subject_identifier,
            report_datetime=subject_visit.report_datetime,
            field_name='panel_name',
            value_str=panel_five.name)

        # check default entry status
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, NOT_REQUIRED)

        # create CRF that triggers rule to REQUIRED
        crf_one = CrfOne.objects.create(
            subject_visit=subject_visit, f1='hello')
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, REQUIRED)

        # change CRF value, reverts to default status
        crf_one.f1 = 'goodbye'
        crf_one.save()
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, NOT_REQUIRED)

        # change CRF value, triggers REQUIRED
        crf_one.f1 = 'hello'
        crf_one.save()
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, REQUIRED)

        # KEY requisition
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_six.name)
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, KEYED)

        # change CRF value
        crf_one.f1 = 'goodbye'
        crf_one.save()

        # assert KEYED value was not changed, rule was ignored
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, KEYED)

    def test_recovers_from_sequence_problem(self):
        """Asserts if instance exists, rule is ignored.
        """
        subject_visit = self.enroll(gender=FEMALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup3)
        Reference.objects.create(
            timepoint=subject_visit.visit_code,
            identifier=subject_visit.subject_identifier,
            report_datetime=subject_visit.report_datetime,
            field_name='panel_name',
            value_str=panel_five.name)

        # create CRF that triggers rule to REQUIRED
        crf_one = CrfOne.objects.create(
            subject_visit=subject_visit, f1='hello')
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, REQUIRED)

        # KEY requisition
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_six.name)
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, KEYED)

        # mess up sequence
        metadata_obj.entry_status = NOT_REQUIRED
        metadata_obj.save()

        # resave to trigger rules
        crf_one.save()

        # assert KEYED value was not changed, rule was ignored
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, KEYED)

    def test_recovers_from_missing_metadata(self):
        subject_visit = self.enroll(gender=FEMALE)
        site_metadata_rules.registry = OrderedDict()
        site_metadata_rules.register(RequisitionRuleGroup3)
        Reference.objects.create(
            timepoint=subject_visit.visit_code,
            identifier=subject_visit.subject_identifier,
            report_datetime=subject_visit.report_datetime,
            field_name='panel_name',
            value_str=panel_five.name)

        # create CRF that triggers rule to REQUIRED
        crf_one = CrfOne.objects.create(
            subject_visit=subject_visit, f1='hello')
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, REQUIRED)

        # KEY requisition
        SubjectRequisition.objects.create(
            subject_visit=subject_visit, panel_name=panel_six.name)
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, KEYED)

        # delete metadata
        metadata_obj.delete()

        # resave to trigger rules
        crf_one.save()

        # assert KEYED value was not changed, rule was ignored
        metadata_obj = RequisitionMetadata.objects.get(
            model='edc_metadata_rules.subjectrequisition',
            subject_identifier=subject_visit.subject_identifier,
            visit_code=subject_visit.visit_code,
            panel_name=panel_six.name)
        self.assertEqual(metadata_obj.entry_status, KEYED)
