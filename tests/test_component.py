from ryzom import html


def test_default_tag_name():
    class MyComponent(html.Component):
        pass

    assert MyComponent().tag == 'my-component'

    # self naming of Component should not break inherited tag names
    class MyDivComponent(html.Div):
        pass
    assert MyDivComponent().tag == 'div'

    # test thread safety of tag override
    assert html.Div(tag='test').tag == 'test'
    assert html.Div().tag == 'div'


def test_declarative_attributes():
    class MyComponent(html.Component):
        attrs = {'type': 'text'}

    assert MyComponent(name='foo').attrs == {'type': 'text', 'name': 'foo'}


def test_declarative_noclose():
    class Foo(html.Div):
        selfclose = True
    assert Foo().selfclose
    assert not Foo(selfclose=False).selfclose


def test_addcls_rmcls():
    class MyComponent(html.Component):
        attrs = {'class': 'foo'}

    assert MyComponent(addcls='bar').attrs['class'] == 'foo bar'

    assert MyComponent(rmcls='foo', addcls='bar').attrs['class'] == 'bar'


class Test1(html.Div):
    attrs = dict(
        x='x',
        y='y',
        z='z',
    )

class Test2(Test1):
    attrs = dict(
        x='xx',
        z=None,
    )


def test_attr_copy():
    # test that we didn't break the class (that attrs were copied)
    assert Test1().attrs is not Test1.attrs


def test_attr_inheritance():
    assert Test1.attrs.x == 'x'
    assert Test2.attrs.x == 'xx'
    assert Test2.attrs.y == 'y'


def test_attr_delete():
    assert 'z' not in Test2.attrs

    test = Test2()
    assert test.attrs.x
    test.attrs.x = None
    assert 'x' not in test.attrs

    test.attrs.lol = None
    assert 'lol' not in test.attrs

def test_attr_instance():
    test = Test1()
    test.attrs.x = None
    assert 'x' not in test.attrs
    # test against any side effect on class
    assert Test1.attrs.x == 'x'


def test_attr_style():
    test = Test1()
    test.attrs.style = 'display: none; color: blue'
    assert test.attrs.style == dict(display='none', color='blue')

    class C1(html.Component):
        attrs = dict(style='display: none; color: blue')
    assert C1.attrs.style == dict(display='none', color='blue')

    class C2(C1):
        attrs = dict(style='display: block')

    assert C1.attrs.style == dict(display='none', color='blue')
    assert C2.attrs.style == dict(display='block', color='blue')


def test_attr_class():
    class C1(html.Component):
        attrs = dict(cls='foo')
    assert C1.attrs['class'] == 'foo'
    assert C1().attrs['class'] == 'foo'

    class C2(C1):
        attrs = dict(addcls='bar')
    assert C2.attrs['class'] == 'foo bar'
    assert C2().attrs['class'] == 'foo bar'

    class C3(C2):
        attrs = dict(rmcls='foo')
    assert C3.attrs['class'] == 'bar'
    assert C3().attrs['class'] == 'bar'

def test_html_payload():
    test = html.HTMLPayload(background_color='white')
    assert [*test.keys()] == ['background-color']
    assert test['background-color'] == 'white'
    assert test.background_color == 'white'

    test.background_position = 'top'
    assert test['background-position'] == 'top'
    assert test.background_position == 'top'
    assert [*test.keys()] == ['background-color', 'background-position']


class BlueWhite(html.Div):
    style = dict(
        background_color='white',
        color='blue',
    )


class RedWhite(BlueWhite):
    style = dict(
        color='red',
    )


def test_component_style():
    assert BlueWhite().attrs.style.background_color == 'white'
    assert BlueWhite().attrs.style.color == 'blue'
    assert RedWhite().attrs.style.background_color == 'white'
    assert RedWhite().attrs.style.color == 'red'

    # test that we don't have side effects from instance to class
    comp = RedWhite()
    comp.attrs.style.color = 'yellow'
    assert comp.attrs.style.color == 'yellow'
    assert RedWhite().attrs.style.color == 'red'

    comp = RedWhite(style='background-color: black; color: green')
    assert comp.attrs.style.background_color == 'black'
    assert comp.attrs.style.color == 'green'
