"""Generate an unapplied native observation patch; never build or run SUMO."""
import re
from textwrap import dedent


TAGS = ['includes', 'start', 'prior', 'candidate', 'finish']
START = b'MSPModel_Striping::PState::PState(MSPerson* person, MSStageMoving* stage, const MSLane* lane):'
STOP = b'MSPModel_Striping::PState::PState(MSPerson* person, MSStageMoving* stage, std::istringstream* in)'


def block(tag, code, indent, newline):
    lines = ['// JDRT_TRACE_BEGIN ' + tag, *dedent(code).strip('\n').splitlines(), '// JDRT_TRACE_END ' + tag]
    return newline.join((indent + line).encode('utf-8') for line in lines) + newline


def insert_once(source, anchor, addition, after=False):
    if source.count(anchor) != 1:
        raise ValueError('Native trace anchor missing or ambiguous')
    return source.replace(anchor, anchor + addition if after else addition + anchor)


def instrument(source):
    if not isinstance(source, bytes) or b'\0' in source or b'JDRT_TRACE_' in source:
        raise ValueError('Expected clean, untraced native source')
    if source.count(START) != 1 or source.count(STOP) != 1 or source.index(START) >= source.index(STOP):
        raise ValueError('Ambiguous native constructor boundary')
    newline = b'\r\n' if b'\r\n' in source else b'\n'
    begin, end = source.index(START), source.index(STOP)
    constructor = source[begin:end]
    start = block('start', r'''
        static unsigned long long jdrtTraceSequence = 0;
        std::ostringstream jdrtTraceStream;
        jdrtTraceStream << std::setprecision(std::numeric_limits<double>::max_digits10)
                        << '<' << "jdrtLatGuard";
        const auto jdrtTraceField = [&](const char* key, const auto& value) {
            jdrtTraceStream << ' ' << key << "=\"" << value << '"';
        };
        jdrtTraceField("seq", ++jdrtTraceSequence);
        jdrtTraceField("sim_step", SIMSTEP);
        jdrtTraceField("person", StringUtils::escapeXML(person->getID()));
        jdrtTraceField("current_edge", StringUtils::escapeXML(currentEdge->getID()));
        jdrtTraceField("current_edge_normal", currentEdge->isNormal());
        jdrtTraceField("new_lane", StringUtils::escapeXML(lane->getID()));
        jdrtTraceField("new_pos", myEdgePos);
        jdrtTraceField("new_dir", myDir);
        jdrtTraceField("input_lat", myPosLat);
        jdrtTraceField("input_unspecified", myPosLat == UNSPECIFIED_POS_LAT);
        jdrtTraceField("input_random", myPosLat == RANDOM_POS_LAT);
        jdrtTraceField("legacy", myLegacyPosLat);
        jdrtTraceField("stages", person->getNumStages());
        jdrtTraceField("remaining", person->getNumRemainingStages());
        jdrtTraceField("new_departed", stage->getDeparted());
    ''', '    ', newline)
    prior = block('prior', r'''
        jdrtTraceField("prior_evaluated", 1);
        jdrtTraceField("prior_type", static_cast<int>(previousStage->getStageType()));
        if (previousStage->getStageType() == MSStageType::WALKING) {
            const MSEdge* jdrtPriorEdge = previousStage->getEdge();
            jdrtTraceField("prior_edge_null", jdrtPriorEdge == nullptr);
            if (jdrtPriorEdge != nullptr) {
                jdrtTraceField("prior_edge", StringUtils::escapeXML(jdrtPriorEdge->getID()));
            }
            jdrtTraceField("edge_same", jdrtPriorEdge == currentEdge);
            if (jdrtPriorEdge == currentEdge) {
                jdrtTraceField("prior_arrived", previousStage->getArrived());
                jdrtTraceField("time_same", previousStage->getArrived() == stage->getDeparted());
            }
        }
    ''', '        ', newline)
    candidate = block('candidate', r'''
        jdrtTraceField("state_evaluated", 1);
        jdrtTraceField("state_null", state == nullptr);
        if (state != nullptr) {
            jdrtTraceField("person_same", state->getPerson() == person);
            if (state->getPerson() == person) {
                jdrtTraceField("prior_person", StringUtils::escapeXML(state->getPerson()->getID()));
                const MSLane* jdrtOldLane = state->getLane();
                jdrtTraceField("old_lane_null", jdrtOldLane == nullptr);
                if (jdrtOldLane != nullptr) {
                    jdrtTraceField("old_lane", StringUtils::escapeXML(jdrtOldLane->getID()));
                }
                jdrtTraceField("lane_same", jdrtOldLane == lane);
                if (jdrtOldLane == lane) {
                    const double jdrtOldPos = state->getEdgePos(SIMSTEP);
                    jdrtTraceField("old_pos", jdrtOldPos);
                    jdrtTraceField("position_same", jdrtOldPos == myEdgePos);
                    if (jdrtOldPos == myEdgePos) {
                        jdrtTraceField("old_lat", state->getPosLat());
                    }
                }
            }
        }
    ''', '            ', newline)
    finish = block('finish', r'''
        jdrtTraceField("inherited", previousState != nullptr);
        jdrtTraceField("final_lat", myPosLat);
        jdrtTraceField("final_dir", myDir);
        std::cout << jdrtTraceStream.str() << "/>" << std::endl;
    ''', '    ', newline)
    constructor = insert_once(constructor, b'    const PState* previousState = nullptr;' + newline, start)
    anchor = b'        const MSStage* previousStage = person->getNextStage(-1);' + newline
    constructor = insert_once(constructor, anchor, prior, after=True)
    anchor = b'            const PState* state = dynamic_cast<const PState*>(previousWalk->getPState());' + newline
    constructor = insert_once(constructor, anchor, candidate, after=True)
    constructor = insert_once(constructor, b'    myNLI = getNextLane(*this, lane, nullptr);' + newline, finish)
    transformed = source[:begin] + constructor + source[end:]
    includes = block('includes', '''
        #include <iomanip>
        #include <limits>
        #include <sstream>
        #include <utils/common/StringUtils.h>
    ''', '', newline)
    transformed = insert_once(transformed, b'#include <config.h>' + newline, includes, after=True)
    if restore(transformed) != source:
        raise ValueError('Diagnostic insertion altered original source')
    return transformed


def restore(source):
    pattern = rb'(?ms)^[ \t]*// JDRT_TRACE_BEGIN ([a-z_]+)\r?\n.*?^[ \t]*// JDRT_TRACE_END \1\r?\n'
    matches = list(re.finditer(pattern, source))
    if ([m[1].decode('ascii') for m in matches] != TAGS
            or source.count(b'JDRT_TRACE_BEGIN') != len(TAGS)
            or source.count(b'JDRT_TRACE_END') != len(TAGS)):
        raise ValueError('Trace blocks missing or ambiguous')
    return re.sub(pattern, b'', source)


def verify(original, instrumented):
    if instrumented != instrument(original) or restore(instrumented) != original:
        raise ValueError('Diagnostic source differs from exact observation generator')
