"""Writes loadtest/handshake.jmx (run:  python loadtest/build_plan.py).

Four scenarios, each its own thread group. Everything is a JMeter property, so one plan
serves 100, 300 or 500 users:  jmeter -n -t handshake.jmx -Jusers=300 -Jhost=localhost
"""

from pathlib import Path
from xml.sax.saxutils import escape

RESUME = "resume.pdf"


def prop(name, default):
    return "${__P(%s,%s)}" % (name, default)


def sampler(name, method, domain, port, path, *, body=None, args=None, file=None, headers=None):
    parts = [f'<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{escape(name)}" enabled="true">']
    if file:
        parts.append('<boolProp name="HTTPSampler.DO_MULTIPART_POST">true</boolProp>')
        parts.append('<elementProp name="HTTPsampler.Files" elementType="HTTPFileArgs"><collectionProp name="HTTPFileArgs.files">'
                     f'<elementProp name="" elementType="HTTPFileArg"><stringProp name="File.path">{escape(file)}</stringProp>'
                     '<stringProp name="File.paramname">resume</stringProp><stringProp name="File.mimetype">application/pdf</stringProp></elementProp>'
                     '</collectionProp></elementProp>')
        parts.append('<elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments"/></elementProp>')
    elif body is not None:
        parts.append('<boolProp name="HTTPSampler.postBodyRaw">true</boolProp>')
        parts.append('<elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments">'
                     f'<elementProp name="" elementType="HTTPArgument"><boolProp name="HTTPArgument.always_encode">false</boolProp>'
                     f'<stringProp name="Argument.value">{escape(body)}</stringProp><stringProp name="Argument.metadata">=</stringProp></elementProp>'
                     '</collectionProp></elementProp>')
    else:
        items = "".join(
            f'<elementProp name="{escape(k)}" elementType="HTTPArgument"><boolProp name="HTTPArgument.always_encode">true</boolProp>'
            f'<stringProp name="Argument.name">{escape(k)}</stringProp><stringProp name="Argument.value">{escape(v)}</stringProp>'
            '<stringProp name="Argument.metadata">=</stringProp><boolProp name="HTTPArgument.use_equals">true</boolProp></elementProp>'
            for k, v in (args or {}).items())
        parts.append(f'<elementProp name="HTTPsampler.Arguments" elementType="Arguments"><collectionProp name="Arguments.arguments">{items}</collectionProp></elementProp>')
    parts.append(f'<stringProp name="HTTPSampler.domain">{domain}</stringProp><stringProp name="HTTPSampler.port">{port}</stringProp>')
    parts.append('<stringProp name="HTTPSampler.protocol">http</stringProp>')
    parts.append(f'<stringProp name="HTTPSampler.path">{escape(path)}</stringProp><stringProp name="HTTPSampler.method">{method}</stringProp>')
    parts.append('<boolProp name="HTTPSampler.follow_redirects">true</boolProp><boolProp name="HTTPSampler.use_keepalive">true</boolProp></HTTPSamplerProxy>')
    tree = ["<hashTree>"]
    if headers:
        hs = "".join(f'<elementProp name="" elementType="Header"><stringProp name="Header.name">{k}</stringProp><stringProp name="Header.value">{escape(v)}</stringProp></elementProp>' for k, v in headers.items())
        tree.append(f'<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="Headers" enabled="true"><collectionProp name="HeaderManager.headers">{hs}</collectionProp></HeaderManager><hashTree/>')
    return "".join(parts), tree


def assertion(codes):
    pats = "".join(f'<stringProp name="{i}">{c}</stringProp>' for i, c in enumerate(codes))
    return ('<ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="Status is expected" enabled="true">'
            f'<collectionProp name="Asserion.test_strings">{pats}</collectionProp><stringProp name="Assertion.custom_message"></stringProp>'
            '<stringProp name="Assertion.test_field">Assertion.response_code</stringProp><boolProp name="Assertion.assume_success">false</boolProp>'
            f'<intProp name="Assertion.test_type">{8 if len(codes) == 1 else 40}</intProp></ResponseAssertion><hashTree/>')


def accept(codes):
    # An assertion can only fail a sample. A 4xx is failed by the HTTP sampler itself, so the
    # expected codes (409 = already applied/registered) must be marked successful here first.
    script = "if (%s.contains(prev.getResponseCode())) { prev.setSuccessful(true) }" % ("[" + ", ".join(f"'{c}'" for c in codes) + "]")
    return ('<JSR223PostProcessor guiclass="TestBeanGUI" testclass="JSR223PostProcessor" testname="Accept expected codes" enabled="true">'
            '<stringProp name="scriptLanguage">groovy</stringProp><stringProp name="parameters"></stringProp>'
            '<stringProp name="filename"></stringProp><stringProp name="cacheKey">true</stringProp>'
            f'<stringProp name="script">{escape(script)}</stringProp></JSR223PostProcessor><hashTree/>')


def extractor(var):
    return ('<JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="Save token" enabled="true">'
            f'<stringProp name="JSONPostProcessor.referenceNames">{var}</stringProp><stringProp name="JSONPostProcessor.jsonPathExprs">$.access_token</stringProp>'
            '<stringProp name="JSONPostProcessor.match_numbers">1</stringProp></JSONPostProcessor><hashTree/>')


def step(name, method, domain, port, path, ok, *, token=None, extract=None, **kw):
    headers = dict(kw.pop("headers", {}) or {})
    if token:
        headers["Authorization"] = "Bearer ${%s}" % token
    xml, tree = sampler(name, method, domain, port, path, headers=headers, **kw)
    inner = "".join(tree[1:]) + (accept(ok) if len(ok) > 1 else "") + assertion(ok) + (extractor(extract) if extract else "")
    return xml + "<hashTree>" + inner + "</hashTree>"


def thread_group(name, steps, loops_prop="loops"):
    return ('<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="%s" enabled="true">'
            '<stringProp name="ThreadGroup.on_sample_error">continue</stringProp>'
            '<elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop" enabled="true">'
            '<boolProp name="LoopController.continue_forever">false</boolProp><stringProp name="LoopController.loops">%s</stringProp></elementProp>'
            '<stringProp name="ThreadGroup.num_threads">%s</stringProp><stringProp name="ThreadGroup.ramp_time">%s</stringProp></ThreadGroup>'
            % (name, prop(loops_prop, 5), prop("users", 100), prop("rampup", 60))
            ) + "<hashTree>" + "".join(steps) + think() + "</hashTree>"


def think():
    return ('<ConstantTimer guiclass="ConstantTimerGui" testclass="ConstantTimer" testname="Think time" enabled="true">'
            f'<stringProp name="ConstantTimer.delay">{prop("think_ms", 500)}</stringProp></ConstantTimer><hashTree/>')


def var(name, value):
    return f'<elementProp name="{name}" elementType="Argument"><stringProp name="Argument.name">{name}</stringProp><stringProp name="Argument.value">{value}</stringProp><stringProp name="Argument.metadata">=</stringProp></elementProp>'


HOST = "${host}"
# each virtual user logs in as one of the 200 seeded students (seed3.student.001 ... 200)
EMAIL = "seed3.student.${__groovy((1000 + (ctx.getThreadNum() % 200) + 1).toString().substring(1))}@demo.p03.example.com"
JSON = {"Content-Type": "application/json"}


def once(inner):
    # a real user logs in once, then keeps using the token
    return ('<OnceOnlyController guiclass="OnceOnlyControllerGui" testclass="OnceOnlyController" testname="Log in once" enabled="true"/>'
            "<hashTree>" + inner + "</hashTree>")


def student_login():
    return once(step("Student login", "POST", HOST, "${student_port}", "/auth/login", ["200"], extract="token",
                headers=JSON, body='{"email":"%s","password":"${password}"}' % EMAIL))


user_vars = "".join([
    var("host", prop("host", "localhost")), var("company_port", prop("company_port", 9030)),
    var("student_port", prop("student_port", 9031)), var("job_port", prop("job_port", 9032)),
    var("application_port", prop("application_port", 9033)), var("event_port", prop("event_port", 9034)),
    var("password", prop("password", "Pair03Demo!2026")),])

groups = [
    thread_group("1 Student login + job search", [
        student_login(),
        step("Search jobs by keyword", "GET", HOST, "${job_port}", "/jobs", ["200"], args={"keyword": "${__RandomString(1,abcdeimnor,)}", "limit": "20"}),
        step("Search jobs by city", "GET", HOST, "${job_port}", "/jobs", ["200"], args={"city": "San Jose", "limit": "20"}),
        step("Job detail", "GET", HOST, "${job_port}", "/jobs/${__Random(1,300)}", ["200", "404"]),
    ]),
    thread_group("2 Submit application", [
        student_login(),
        # 201 = submitted, 409 = this student already applied to that job (seed data overlaps)
        step("Apply with resume", "POST", HOST, "${application_port}", "/jobs/${__Random(1,300)}/applications", ["201", "409"],
             token="token", file=RESUME),
        step("My applications", "GET", HOST, "${application_port}", "/applications/me", ["200"], token="token"),
    ]),
    thread_group("3 Event search + registration", [
        student_login(),
        step("Search events", "GET", HOST, "${event_port}", "/events", ["200"], args={"keyword": "Pair03"}),
        # 201 = registered, 409 = already registered, 404 = event id missing or already past
        step("Register for event", "POST", HOST, "${event_port}", "/events/${__Random(1,100)}/registrations", ["201", "409", "404"], token="token"),
    ]),
    thread_group("4 Company login + dashboard", [
        once(step("Company login", "POST", HOST, "${company_port}", "/api/companies/auth/login", ["200"], extract="ctoken", headers=JSON,
                  body='{"email":"seed3.company.001@demo.p03.example.com","password":"${password}"}')),
        step("Company jobs", "GET", HOST, "${job_port}", "/api/companies/jobs", ["200"], token="ctoken"),
        step("Company events", "GET", HOST, "${event_port}", "/api/companies/events", ["200"], token="ctoken"),
    ]),
]

plan = ('<?xml version="1.0" encoding="UTF-8"?><jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3"><hashTree>'
        '<TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="Pair 03 Handshake load test" enabled="true">'
        '<boolProp name="TestPlan.functional_mode">false</boolProp><boolProp name="TestPlan.serialize_threadgroups">false</boolProp>'
        f'<elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="Variables" enabled="true"><collectionProp name="Arguments.arguments">{user_vars}</collectionProp></elementProp>'
        '</TestPlan><hashTree>' + "".join(groups) + '</hashTree></hashTree></jmeterTestPlan>')

Path(__file__).with_name("handshake.jmx").write_text(plan)
print("wrote handshake.jmx")
