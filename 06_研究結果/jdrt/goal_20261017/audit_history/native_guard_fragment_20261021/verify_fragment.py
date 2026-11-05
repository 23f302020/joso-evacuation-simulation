"""Compile the verbatim guard with artificial C++ objects, never a SUMO world."""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
BASE = Path(__file__).parent
NATIVE = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
SOURCE = NATIVE / 'sources/sumo-fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3/src/microsim/transportables/MSPModel_Striping.cpp'
COMPILER = Path('C:/Ruby31-x64/msys64/ucrt64/bin/g++.exe')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


HEADER = r"""
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
enum class MSStageType { OTHER = -1, WALKING = WALKING_VALUE };
constexpr long long SIMSTEP = 7;
constexpr double UNSPECIFIED_POS_LAT = std::numeric_limits<double>::max();
struct Edge { bool normal = true; bool isNormal() const { return normal; } };
struct Lane {};
struct Person;
struct Backend { virtual ~Backend() = default; };
struct PState : Backend {
    const Person* owner = nullptr;
    const Lane* ownLane = nullptr;
    double pos = 3.5, lateral = 0.8;
    const Person* getPerson() const { return owner; }
    const Lane* getLane() const { return ownLane; }
    double getEdgePos(long long) const { return pos; }
    double getPosLat() const { return lateral; }
};
struct MSStage {
    virtual ~MSStage() = default;
    MSStageType type = MSStageType::WALKING;
    const Edge* edge = nullptr;
    long long arrived = SIMSTEP;
    MSStageType getStageType() const { return type; }
    const Edge* getEdge() const { return edge; }
    long long getArrived() const { return arrived; }
};
struct MSStageMoving : MSStage {
    const Backend* state = nullptr;
    long long departed = SIMSTEP;
    const Backend* getPState() const { return state; }
    long long getDeparted() const { return departed; }
};
struct Person {
    int stages = 2, remaining = 1;
    bool forbidPrior = false;
    const MSStage* prior = nullptr;
    int getNumStages() const { return stages; }
    int getNumRemainingStages() const { return remaining; }
    const MSStage* getNextStage(int index) const {
        if (index != -1 || forbidPrior || prior == nullptr) {
            throw std::runtime_error("guard illegally accessed prior stage");
        }
        return prior;
    }
};
const PState* select_previous(double myPosLat, bool myLegacyPosLat,
        const Edge* currentEdge, const Person* person, const Lane* lane,
        const MSStageMoving* stage, double myEdgePos) {
"""

TAIL = r"""
    return previousState;
}
int main() {
    const char* names[] = {
        "eligible", "explicit_lateral", "random_lateral", "legacy",
        "internal_edge", "no_prior", "prior_not_walking", "different_edge",
        "different_time", "null_state", "different_backend_type",
        "different_person", "different_lane", "different_position",
        "null_old_lane", "nonfinite_old_position"
    };
    for (int mode = 0; mode < 16; ++mode) {
        Edge current, otherEdge;
        Lane lane, otherLane;
        Person person, otherPerson;
        PState priorState;
        Backend differentBackend;
        MSStageMoving priorStage, nextStage;
        priorState.owner = &person;
        priorState.ownLane = &lane;
        priorStage.edge = &current;
        priorStage.state = &priorState;
        person.prior = &priorStage;
        double inputLat = UNSPECIFIED_POS_LAT;
        bool legacy = false;
        switch (mode) {
            case 1: inputLat = 0.3; person.forbidPrior = true; break;
            case 2: inputLat = -UNSPECIFIED_POS_LAT; person.forbidPrior = true; break;
            case 3: legacy = true; person.forbidPrior = true; break;
            case 4: current.normal = false; person.forbidPrior = true; break;
            case 5: person.stages = person.remaining; person.forbidPrior = true; break;
            case 6: priorStage.type = MSStageType::OTHER; break;
            case 7: priorStage.edge = &otherEdge; break;
            case 8: priorStage.arrived = SIMSTEP - 1; break;
            case 9: priorStage.state = nullptr; break;
            case 10: priorStage.state = &differentBackend; break;
            case 11: priorState.owner = &otherPerson; break;
            case 12: priorState.ownLane = &otherLane; break;
            case 13: priorState.pos += 1; break;
            case 14: priorState.ownLane = nullptr; break;
            case 15: priorState.pos = std::numeric_limits<double>::quiet_NaN(); break;
        }
        const PState* selected = select_previous(inputLat, legacy, &current,
                &person, &lane, &nextStage, 3.5);
        if ((mode == 0 && selected != &priorState) || (mode != 0 && selected != nullptr)) {
            std::cerr << "GUARD_CASE_FAILED " << names[mode] << "\n";
            return 2;
        }
        std::cout << "GUARD_CASE_PASS " << names[mode] << "\n";
    }
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,24}', args.attempt):
        raise ValueError('A fresh short artificial test attempt is required')
    folder = BASE / args.attempt
    folder.mkdir(exist_ok=False)
    report = {'at_jst': datetime.now().astimezone().isoformat(),
              'scope': 'Verbatim production C++ guard in artificial polymorphic objects; not native SUMO execution',
              'source': str(SOURCE), 'source_sha256': sha(SOURCE),
              'compiler': str(COMPILER), 'compiler_sha256': sha(COMPILER),
              'script_sha256': sha(Path(__file__)), 'commands': [],
              'technical_ready': False, 'research_adoption_permitted': False,
              'native_false_guard_observed': False}
    try:
        review_path = ROOT / '06_研究結果/jdrt/goal_20261017/audit_history/native_trace_source_20261021/review.json'
        review = json.loads(review_path.read_bytes())
        if report['source_sha256'] != review['base_cpp_sha256']:
            raise ValueError('Production source differs from the independently bound base source')
        report['source_review_sha256'] = sha(review_path)
        raw = SOURCE.read_bytes()
        begin = b'    const PState* previousState = nullptr;'
        end = b'    if (previousState != nullptr) {'
        if raw.count(begin) != 1 or raw.count(end) != 1:
            raise ValueError('Ambiguous or changed native guard boundary')
        body_bytes = raw[raw.index(begin):raw.index(end)]
        (folder / 'verbatim_guard.txt').write_bytes(body_bytes)
        report['verbatim_guard_sha256'] = hashlib.sha256(body_bytes).hexdigest()
        body = body_bytes.decode('utf-8')
        constants_path = ROOT / '06_研究結果/jdrt/goal_20261017/audit_history/native_internal_fixture_20261021/guard_plan.json'
        constants = json.loads(constants_path.read_bytes())['constants']
        walking_type = constants['walking_type']
        if type(walking_type) is not int or walking_type < 0:
            raise ValueError('Source-bound walking stage enum is required')
        report['constant_plan_sha256'] = sha(constants_path)
        header = HEADER.replace('WALKING_VALUE', str(walking_type))
        time_guard = '&& previousStage->getArrived() == stage->getDeparted()'
        position_guard = '&& state->getEdgePos(SIMSTEP) == myEdgePos'
        if body.count(time_guard) != 1 or body.count(position_guard) != 1:
            raise ValueError('Expected exact time and longitudinal guard predicates')
        variants = [
            ('omitted_time', body.replace(time_guard, '&& true /* artificial missing-time mutant */'), 'different_time'),
            ('omitted_position', body.replace(position_guard, '&& true /* artificial missing-position mutant */'), 'different_position'),
            ('exact_source', body, None),
        ]
        env = {**os.environ, 'PATH': str(COMPILER.parent) + ';C:/Windows/System32;C:/Windows'}
        for name, fragment, expected_failure in variants:
            cpp, binary = folder / (name + '.cpp'), folder / (name + '.exe')
            cpp.write_text(header + fragment + TAIL, encoding='utf-8', newline='\n')
            command = [str(COMPILER), '-std=c++17', '-O2', '-DNDEBUG',
                       '-static', '-static-libgcc', '-static-libstdc++', str(cpp), '-o', str(binary)]
            compiled = subprocess.run(command, capture_output=True, env=env)
            (folder / (name + '.compile.stdout.log')).write_bytes(compiled.stdout)
            (folder / (name + '.compile.stderr.log')).write_bytes(compiled.stderr)
            report['commands'].append({'kind': 'compile', 'command': command, 'exit_code': compiled.returncode,
                                       'source_sha256': sha(cpp)})
            if compiled.returncode:
                raise RuntimeError('Artificial guard harness failed compilation: ' + name)
            ran = subprocess.run([str(binary)], capture_output=True, env=env)
            (folder / (name + '.stdout.log')).write_bytes(ran.stdout)
            (folder / (name + '.stderr.log')).write_bytes(ran.stderr)
            report['commands'].append({'kind': 'artificial_cpp_contract', 'command': [str(binary)],
                                       'exit_code': ran.returncode, 'binary_sha256': sha(binary)})
            if expected_failure:
                if ran.returncode != 2 or ran.stderr.strip() != ('GUARD_CASE_FAILED ' + expected_failure).encode():
                    raise RuntimeError('Missing-guard mutant was not rejected by its intended contract')
            elif ran.returncode or len(ran.stdout.splitlines()) != 16:
                raise RuntimeError('Verbatim guard failed an artificial contract')
        if sha(SOURCE) != report['source_sha256'] or sha(COMPILER) != report['compiler_sha256']:
            raise RuntimeError('Bound production source/compiler changed during artificial testing')
        report.update(status='COMPILED_VERBATIM_GUARD_16_ARTIFICIAL_CASES_PASS_AND_TWO_MUTANTS_REJECTED',
                      native_branch_coverage_claim='None: native12/13 observations remain separately reported',
                      unproved='Full native ABI/layout, every valid SUMO API path, actual false-guard reachability, transitive compiler reproducibility')
    except BaseException as error:
        report.update(status='FAILED_PRESERVED', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        report['finished_at_jst'] = datetime.now().astimezone().isoformat()
        report['artifacts_sha256'] = {p.name: sha(p) for p in folder.iterdir() if p.is_file()}
        with (folder / 'report.json').open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'status': report['status'], 'report': str(folder / 'report.json'),
                      'native_false_guard_observed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
