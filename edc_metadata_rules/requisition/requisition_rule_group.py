from collections import OrderedDict, namedtuple

from edc_metadata import REQUISITION
from edc_metadata.requisition import RequisitionMetadataUpdater

from ..rule_group_meta_options import RuleGroupMetaOptions
from ..rule_group_metaclass import RuleGroupMetaclass

RuleResult = namedtuple('RuleResult', 'target_panel entry_status')


class RequisitionRuleGroupMetaOptionsError(Exception):
    pass


class RequisitionRuleGroupMetaOptions(RuleGroupMetaOptions):

    def __init__(self, group_name, attrs):
        super().__init__(group_name, attrs)
        self.requisition_model = self.options.get('requisition_model')
        if self.requisition_model:
            try:
                assert len(self.requisition_model.split('.')) == 2
            except AssertionError:
                self.requisition_model = f'{self.app_label}.{self.requisition_model}'
                self.options.update(requisition_model=self.requisition_model)
            self.options.update(
                target_models=[self.requisition_model])
            rules = {k: v for k, v in attrs.items() if not k.startswith('_')}
            if self.requisition_model == self.source_model:
                for name, rule in rules.items():
                    if not rule.source_panel:
                        raise RequisitionRuleGroupMetaOptionsError(
                            f'Rule expects "source_panel". Got '
                            f'requisition_model="{self.requisition_model}", '
                            f'source_model="{self.source_model}". '
                            f'See {group_name}.{name}.')
            else:
                for name, rule in rules.items():
                    if rule.source_panel:
                        raise RequisitionRuleGroupMetaOptionsError(
                            f'Rule does not expect "source_panel". Got '
                            f'requisition_model="{self.requisition_model}", '
                            f'source_model="{self.source_model}". '
                            f'See {group_name}.{name}.')

    @property
    def default_meta_options(self):
        opts = super().default_meta_options
        opts.extend(['requisition_model'])
        return opts


class RequisitionMetaclass(RuleGroupMetaclass):

    rule_group_meta = RequisitionRuleGroupMetaOptions


class RequisitionRuleGroup(object, metaclass=RequisitionMetaclass):

    metadata_updater_cls = RequisitionMetadataUpdater
    metadata_category = REQUISITION

    @classmethod
    def evaluate_rules(cls, visit=None):
        """Returns a tuple of (rule_results, metadata_objects) where
        rule_results ...
        """
        rule_results = OrderedDict()
        metadata_objects = OrderedDict()
        metadata_updater = cls.metadata_updater_cls(
            visit=visit, metadata_category=cls.metadata_category)
        for rule in cls._meta.options.get('rules'):
            rule_results[str(rule)] = OrderedDict()
            for target_model, entry_status in rule.run(visit=visit).items():
                rule_results[str(rule)].update({target_model: []})
                target_panels = cls.get_target_panels(rule=rule, visit=visit)
                for target_panel in target_panels:
                    metadata_object = metadata_updater.update(
                        target_model=target_model,
                        target_panel=target_panel,
                        entry_status=entry_status)
                    metadata_objects.update(
                        {target_panel: metadata_object})
                    rule_results[str(rule)][target_model].append(
                        RuleResult(target_panel, entry_status))
        return rule_results, metadata_objects

    @classmethod
    def get_target_panels(cls, rule=None, visit=None):
        """Returns a list of target panel names -- those rule panels
        included in this visit.

        Note: rules should only attempt to update metadata for
        the rule's target_panels also in visit.requisitions.
        """
        target_panels = []
        panels_for_visit = [r.panel.name for r in visit.visit.requisitions]
        for panel_name in rule.target_panels:
            if panel_name in panels_for_visit:
                target_panels.append(panel_name)
        return target_panels
