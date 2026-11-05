"""Compile the actual native history loop in a small algebraic contract harness.

This verifies index mapping only. It does not simulate vehicle physics.
"""
import argparse
import os
from pathlib import Path
import subprocess
from choice_native_stop_index_remap import remap_source


def main(source, output, candidate):
    original = source.read_bytes()
    raw = remap_source(original) if candidate else original
    text = raw.decode('utf-8')
    start = text.index('    for (StopParVector::iterator it = myPastStops.begin();')
    end = text.index('    // if we did not drive yet', start)
    loop = text[start:end]
    program = r'''#include <vector>
#include <string>
#include <map>
#include <iostream>
#include <algorithm>
struct MSEdge { std::string id; static const MSEdge* dictionary(const std::string&); };
const MSEdge A{"a"}, B{"b"}, C{"c"}, D{"d"};
const MSEdge* MSEdge::dictionary(const std::string& id) {
    static std::map<std::string,const MSEdge*> edges{{"a",&A},{"b",&B},{"c",&C},{"d",&D}};
    return edges.at(id);
}
struct MSLane { static const MSLane* dictionary(const std::string&) { throw 1; }
    const MSEdge& getEdge() const { throw 1; } };
struct Stop { std::string edge, lane; int routeIndex; };
using StopParVector=std::vector<Stop>;
struct Route { std::vector<const MSEdge*> edges;
    auto begin() const { return edges.begin(); } auto end() const { return edges.end(); }
    const auto& getEdges() const { return edges; } };
std::vector<int> project(Route route, int current, int previousCurrentIndex, StopParVector myPastStops) {
    auto myRoute=&route;
    auto myCurrEdge=myRoute->begin()+current;
''' + loop + r'''
    std::vector<int> result;
    for (const auto& stop:myPastStops) result.push_back(stop.routeIndex);
    return result;
}
int main() {
    int failed=0;
    auto check=[&](const char* name, std::vector<int> actual,std::vector<int> expected) {
        bool pass=actual==expected; std::cout<<name<<" "<<(pass?"PASS":"FAIL")<<std::endl; failed+=!pass;
    };
    check("shortened_source_stop_rebased",project({{&C,&D}},0,7,{{"c","",7}}),{0});
    check("unchanged_loop_preserves_actual_earlier_occurrence",project({{&A,&B,&A,&C,&D}},3,3,{{"a","",0}}),{0});
    check("future_same_edge_is_not_a_past_stop",project({{&C,&A,&D}},0,7,{{"a","",2}}),{});
    check("mismatched_edge_at_projected_index_is_removed",project({{&C,&D}},0,7,{{"a","",7}}),{});
    check("retained_prefix_offset",project({{&A,&B,&C,&D}},2,7,{{"a","",5},{"c","",7}}),{0,2});
    check("invalid_future_index_removed",project({{&C,&D}},0,7,{{"d","",9}}),{});
    check("empty_history",project({{&C,&D}},0,7,{}),{});
    return failed?1:0;
}
'''
    output.mkdir(parents=True, exist_ok=False)
    cpp=output/'contract.cpp'
    cpp.write_text(program,encoding='utf-8')
    compiler=Path('C:/Ruby31-x64/msys64/ucrt64/bin/g++.exe')
    exe=output/'contract.exe'
    env=os.environ.copy()
    env['PATH']=str(compiler.parent)+';C:/Windows/System32;C:/Windows'
    with (output/'compile.log').open('xb') as stream:
        code=subprocess.run([str(compiler),'-std=c++17',str(cpp),'-o',str(exe)],env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
    if code: raise RuntimeError('Harness compilation failed; not a contract RED')
    with (output/'result.log').open('xb') as stream:
        code=subprocess.run([str(exe)],env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
    print((output/'result.log').read_text())
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true')
    args=parser.parse_args()
    raise SystemExit(main(args.source,args.output,args.candidate))
