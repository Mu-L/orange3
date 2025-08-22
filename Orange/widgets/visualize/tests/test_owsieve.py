# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring, protected-access
from math import isnan
import unittest
from unittest.mock import patch

import numpy as np

from AnyQt.QtCore import QEvent, QPointF, Qt
from AnyQt.QtGui import QMouseEvent

from Orange.data import ContinuousVariable, DiscreteVariable, Domain, Table
from Orange.widgets.tests.base import WidgetTest, WidgetOutputsTestMixin
from Orange.widgets.tests.utils import simulate
from Orange.widgets.visualize.owsieve import OWSieveDiagram
from Orange.widgets.visualize.owsieve import ChiSqStats
from Orange.widgets.visualize.owsieve import Discretize
from Orange.widgets.widget import AttributeList


class TestOWSieveDiagram(WidgetTest, WidgetOutputsTestMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        WidgetOutputsTestMixin.init(cls)

        cls.signal_name = OWSieveDiagram.Inputs.data
        cls.signal_data = cls.data
        cls.titanic = Table("titanic")
        cls.iris = Table("iris")

    def setUp(self):
        self.widget = self.create_widget(OWSieveDiagram)

    def test_context_settings(self):
        # Set titanic and check first two attributes on display
        self.send_signal(self.widget.Inputs.data, self.titanic)
        self.assertEqual(self.widget.attr_x, self.titanic.domain.class_var)
        self.assertEqual(self.widget.attr_y, self.titanic.domain.attributes[0])
        # Change attributes to two different ones
        self.widget.attr_x = self.titanic.domain.attributes[1]
        self.widget.attr_y = self.titanic.domain.attributes[2]
        # Remove data signal
        self.send_signal(self.widget.Inputs.data, None)
        self.assertEqual(self.widget.attr_x, None)
        self.assertEqual(self.widget.attr_y, None)
        self.assertIsNone(self.widget.discrete_data)
        # Set data back to titanic and check if selected attributes are
        # remembered in the settings
        self.send_signal(self.widget.Inputs.data, self.titanic)
        self.assertEqual(self.widget.attr_x, self.titanic.domain.attributes[1])
        self.assertEqual(self.widget.attr_y, self.titanic.domain.attributes[2])

    def test_continuous_data(self):
        self.send_signal(self.widget.Inputs.data, self.iris)
        self.assertEqual(self.widget.attr_x, self.iris.domain.class_var)
        self.assertEqual(self.widget.attr_y, self.iris.domain.attributes[0])
        self.assertTrue(self.widget.discrete_data.domain[0].is_discrete)

    def test_few_attributes(self):
        # Test widget behaviour when data has only a few attributes
        # Test for 2 attributes
        attr2 = self.titanic.domain[:2]
        domain2 = Domain(attr2)
        data2 = self.titanic.transform(domain2)
        self.send_signal(self.widget.Inputs.data, data2)
        # Test for 1 attributes
        attr1 = self.titanic.domain[:1]
        domain1 = Domain(attr1)
        data1 = self.titanic.transform(domain1)
        self.send_signal(self.widget.Inputs.data, data1)
        # Test for 0 attributes
        attr0 = self.titanic.domain[:0]
        domain0 = Domain(attr0)
        data0 = self.titanic.transform(domain0)
        self.send_signal(self.widget.Inputs.data, data0)

    def _select_data(self):
        self.widget.attr_x, self.widget.attr_y = self.data.domain[:2]
        area = self.widget.areas[0]
        self.widget.select_area(area, QMouseEvent(
            QEvent.MouseButtonPress, QPointF(), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        return [0, 4, 6, 7, 11, 17, 19, 21, 22, 24, 26, 39, 40, 43, 44, 46]

    def test_missing_values(self):
        """Check widget for dataset with missing values"""
        attrs = [DiscreteVariable("c1", ["a", "b", "c"])]
        class_var = DiscreteVariable("cls", [])
        X = np.array([1, 2, 0, 1, 0, 2])[:, None]
        data = Table(Domain(attrs, class_var), X, np.array([np.nan] * 6))
        self.send_signal(self.widget.Inputs.data, data)

    def test_single_line(self):
        """
        Check if it works when a table has only one row or duplicates.
        Discretizer must have remove_const set to False.
        """
        data = self.titanic[0:1]
        self.send_signal(self.widget.Inputs.data, data)

    def test_chisquare(self):
        """
        Check if it can calculate chi square when there are no attributes
        which suppose to be.
        """
        a = DiscreteVariable("a", values=("y", "n"))
        b = DiscreteVariable("b", values=("y", "n", "o"))
        table = Table.from_list(Domain([a, b]), list(zip("yynny", "ynyyn")))
        chi = ChiSqStats(table, 0, 1)
        self.assertFalse(isnan(chi.chisq))

    def test_cochran_indicator(self):
        # 1) Data that PASS Cochran: balanced 3x3 (expected ~6.67)
        a = DiscreteVariable("A", values=("a1", "a2", "a3"))
        b = DiscreteVariable("B", values=("b1", "b2", "b3"))
        rows_ok = ["a1"]*20 + ["a2"]*20 + ["a3"]*20
        cols_ok = ["b1"]*20 + ["b2"]*20 + ["b3"]*20
        table_ok = Table.from_list(Domain([a, b]), list(zip(rows_ok, cols_ok)))

        self.send_signal(self.widget.Inputs.data, table_ok)
        self.widget.attr_x, self.widget.attr_y = a, b
        self.widget.update_graph()
        # Ensure Cochran was actually evaluated
        self.assertIsNotNone(getattr(self.widget, "_cochran_ok", None))
        self.assertTrue(self.widget._cochran_ok)

        # 2) Data that FAIL Cochran: 3 expected cells < 5 (e.g. 10/20/30 vs 20/20/20)
        rows_bad = ["a1"]*10 + ["a2"]*20 + ["a3"]*30
        cols_bad = ["b1"]*20 + ["b2"]*20 + ["b3"]*20
        table_bad = Table.from_list(Table.from_list(Domain([a, b]), list(zip(rows_bad, cols_bad))).domain,
                                    list(zip(rows_bad, cols_bad)))

        self.send_signal(self.widget.Inputs.data, table_bad)
        # Re-assign attrs in case the widget resets them in handle signals
        self.widget.attr_x, self.widget.attr_y = a, b
        self.widget.update_graph()

        self.assertIsNotNone(getattr(self.widget, "_cochran_ok", None))
        self.assertFalse(self.widget._cochran_ok)

    def test_metadata(self):
        """
        Widget should interpret meta data which are continuous or discrete in
        the same way as features or target. However still one variable should
        be target or feature.
        """
        table = Table.from_list(
            Domain(
                [],
                [],
                [ContinuousVariable("a"),
                 DiscreteVariable("b", values=("y", "n"))]
            ),
            list(zip(
                [42.48, 16.84, 15.23, 23.8],
                "yynn"))
        )
        with patch("Orange.widgets.visualize.owsieve.Discretize",
                   wraps=Discretize) as disc:
            self.send_signal(self.widget.Inputs.data, table)
            self.assertTrue(disc.called)
        metas = self.widget.discrete_data.domain.metas
        self.assertEqual(len(metas), 2)
        self.assertTrue(all(attr.is_discrete for attr in metas))

    def test_sparse_data(self):
        """
        Sparse support.
        """
        self.send_signal(self.widget.Inputs.data, self.iris)
        self.assertEqual(len(self.widget.discrete_data.domain.variables),
                         len(self.iris.domain.variables))
        output = self.get_output(self.widget.Inputs.data)
        self.assertFalse(output.is_sparse())

        table = self.iris.to_sparse()
        self.send_signal(self.widget.Inputs.data, table)
        self.assertEqual(len(self.widget.discrete_data.domain.variables), 2)
        output = self.get_output(self.widget.Inputs.data)
        self.assertTrue(output.is_sparse())

    @patch('Orange.widgets.visualize.owsieve.SieveRank.auto_select')
    def test_vizrank_receives_manual_change(self, auto_select):
        # Recreate the widget so the patch kicks in
        self.widget = self.create_widget(OWSieveDiagram)
        data = Table("iris.tab")
        self.send_signal(self.widget.Inputs.data, data)
        model = self.widget.controls.attr_x.model()
        self.widget.attr_x = model[2]
        self.widget.attr_y = model[3]
        simulate.combobox_activate_index(self.widget.controls.attr_x, 4)
        call_args = auto_select.call_args[0][0]
        self.assertEqual([v.name for v in call_args],
                         [data.domain[2].name, data.domain[1].name])

    def test_input_features(self):
        self.assertTrue(self.widget.attr_box.isEnabled())
        self.send_signal(self.widget.Inputs.data, self.iris)

        # Force a known initial state different from the incoming features
        a0, a1, a2, a3 = self.iris.domain.attributes
        self.widget.attr_x, self.widget.attr_y = a2, a3

        # Send features -> triggers set_input_features -> resolve_shown_attributes
        feats = AttributeList([a0, a1])
        self.send_signal(self.widget.Inputs.features, feats)

        # Attributes should now follow the provided features
        self.assertEqual((self.widget.attr_x, self.widget.attr_y), (a0, a1))

        # Existing checks
        self.assertFalse(self.widget.attr_box.isEnabled())
        self.assertFalse(self.widget.vizrank_button().isEnabled())

        # Remove features -> widget returns to interactive mode
        self.send_signal(self.widget.Inputs.features, None)
        self.assertTrue(self.widget.attr_box.isEnabled())
        self.assertTrue(self.widget.vizrank_button().isEnabled())


if __name__ == "__main__":
    unittest.main()
