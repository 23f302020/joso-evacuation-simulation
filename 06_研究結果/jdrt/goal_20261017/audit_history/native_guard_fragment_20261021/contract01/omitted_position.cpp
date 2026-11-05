
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
enum class MSStageType { OTHER = -1, WALKING = 2 };
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
    const PState* previousState = nullptr;
    if (myPosLat == UNSPECIFIED_POS_LAT && !myLegacyPosLat && currentEdge->isNormal()
            && person->getNumStages() > person->getNumRemainingStages()) {
        const MSStage* previousStage = person->getNextStage(-1);
        if (previousStage->getStageType() == MSStageType::WALKING
                && previousStage->getEdge() == currentEdge
                && previousStage->getArrived() == stage->getDeparted()) {
            const MSStageMoving* previousWalk = static_cast<const MSStageMoving*>(previousStage);
            const PState* state = dynamic_cast<const PState*>(previousWalk->getPState());
            if (state != nullptr && state->getPerson() == person && state->getLane() == lane
                    && true /* artificial missing-position mutant */) {
                previousState = state;
            }
        }
    }

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
